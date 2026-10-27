"""Read-only PPTX object inventory. Flags guide visual review, not a pass/fail grade."""

import argparse
import json
import posixpath
from pathlib import Path
from zipfile import ZipFile, BadZipFile
import xml.etree.ElementTree as ET


NS = {
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main',
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'c': 'http://schemas.openxmlformats.org/drawingml/2006/chart',
}


def number(node, child, attr):
    return float(node.find('a:' + child, NS).attrib[attr])


def transformed(node):
    return (int(node.get('rot', '0')) % 21600000 != 0
            or node.get('flipH') in ('1', 'true')
            or node.get('flipV') in ('1', 'true'))


def group_transform(group, parent):
    x = group.find('p:grpSpPr/a:xfrm', NS)
    if x is None:
        return parent
    if parent is None or transformed(x):
        return None
    try:
        sx = number(x, 'ext', 'cx') / number(x, 'chExt', 'cx')
        sy = number(x, 'ext', 'cy') / number(x, 'chExt', 'cy')
        tx = number(x, 'off', 'x') - number(x, 'chOff', 'x') * sx
        ty = number(x, 'off', 'y') - number(x, 'chOff', 'y') * sy
    except (AttributeError, KeyError, ValueError, ZeroDivisionError):
        return None
    px, py, ox, oy = parent
    return px * sx, py * sy, ox + px * tx, oy + py * ty


def image_coverage(shape, transform, width, height):
    x = shape.find('p:spPr/a:xfrm', NS)
    if x is None or transform is None or transformed(x):
        return None
    try:
        sx, sy, tx, ty = transform
        left = tx + sx * number(x, 'off', 'x')
        top = ty + sy * number(x, 'off', 'y')
        right = left + sx * number(x, 'ext', 'cx')
        bottom = top + sy * number(x, 'ext', 'cy')
    except (AttributeError, KeyError, ValueError):
        return None
    left, right = sorted((left, right))
    top, bottom = sorted((top, bottom))
    area = max(0, min(right, width) - max(left, 0))
    area *= max(0, min(bottom, height) - max(top, 0))
    return area / (width * height)


def slide_inventory(root, width, height):
    result = {key: 0 for key in (
        'native_shape_objects', 'native_text_boxes', 'native_text_characters',
        'connectors', 'picture_objects', 'graphic_frames', 'groups',
        'native_tables', 'native_charts', 'table_cells',
        'image_filled_shapes', 'linked_image_references')}
    result.update(page_covering_image_candidates=[], unmeasured_images=[], warnings=[])
    bg = root.find('p:cSld/p:bg', NS)
    result['slide_background_image'] = bg is not None and bg.find('.//a:blip', NS) is not None

    def visit(container, transform):
        for item in container:
            kind = item.tag.rsplit('}', 1)[-1]
            if kind == 'grpSp':
                result['groups'] += 1
                visit(item, group_transform(item, transform))
                continue
            if kind not in ('sp', 'cxnSp', 'pic', 'graphicFrame'):
                continue
            key = {'sp': 'native_shape_objects', 'cxnSp': 'connectors',
                   'pic': 'picture_objects', 'graphicFrame': 'graphic_frames'}[kind]
            result[key] += 1
            text_body = item.find('p:txBody', NS)
            if text_body is not None:
                text = ''.join(t.text or '' for t in text_body.findall('.//a:t', NS))
                if text.strip():
                    result['native_text_boxes'] += 1
                    result['native_text_characters'] += len(text.strip())
            result['native_tables'] += len(item.findall('.//a:tbl', NS))
            result['native_charts'] += len(item.findall('.//c:chart', NS))
            result['table_cells'] += len(item.findall('.//a:tc', NS))
            blips = item.findall('.//a:blip', NS)
            result['linked_image_references'] += sum(
                '{' + NS['r'] + '}link' in b.attrib for b in blips)
            if not blips:
                continue
            if kind == 'sp':
                result['image_filled_shapes'] += 1
            prop = item.find('.//p:cNvPr', NS)
            name = prop.get('name', kind) if prop is not None else kind
            coverage = image_coverage(item, transform, width, height)
            if coverage is None:
                result['unmeasured_images'].append(name)
            elif coverage >= 0.9:
                result['page_covering_image_candidates'].append(
                    {'name': name, 'visible_page_coverage': round(coverage, 4)})

    tree = root.find('p:cSld/p:spTree', NS)
    if tree is None:
        raise ValueError('Slide is missing its shape tree')
    visit(tree, (1, 1, 0, 0))
    result['total_objects_excluding_groups'] = sum(result[key] for key in (
        'native_shape_objects', 'connectors', 'picture_objects', 'graphic_frames'))
    if result['page_covering_image_candidates'] or result['slide_background_image']:
        result['warnings'].append('Review large images/background: content screenshot or intentional artwork?')
    if result['unmeasured_images']:
        result['warnings'].append('Some image bounds could not be measured; inspect their size visually.')
    if result['linked_image_references']:
        result['warnings'].append('Linked images may depend on external files; confirm embedded copies.')
    if not result['native_text_boxes']:
        result['warnings'].append('No nonempty native text boxes; compare with text visible in the input.')
    return result


def inspect(pptx):
    with ZipFile(pptx) as package:
        presentation = ET.fromstring(package.read('ppt/presentation.xml'))
        size = presentation.find('p:sldSz', NS)
        width, height = int(size.attrib['cx']), int(size.attrib['cy'])
        if width <= 0 or height <= 0:
            raise ValueError('Invalid slide dimensions')
        rels = ET.fromstring(package.read('ppt/_rels/presentation.xml.rels'))
        targets = {r.attrib['Id']: r.attrib['Target'] for r in rels
                   if r.get('TargetMode') != 'External'}
        slides = []
        for index, slide in enumerate(presentation.findall('p:sldIdLst/p:sldId', NS), 1):
            target = targets[slide.attrib['{' + NS['r'] + '}id']]
            part = posixpath.normpath(posixpath.join('ppt', target)) if not target.startswith('/') else target[1:]
            result = slide_inventory(ET.fromstring(package.read(part)), width, height)
            slides.append({'slide': index, 'part': part, **result})
        return {
            'file': str(Path(pptx).resolve()), 'slide_count': len(slides),
            'slide_size_emu': [width, height], 'slides': slides,
            'limits': [
                'Object inventory is not proof of fidelity, legibility or full editability.',
                'Masters/layouts are not expanded. Review inherited artwork and placeholders visually.',
                'Image bounds with rotation/reflection or missing transforms require visual review.',
                'Connector counts do not prove endpoint binding; text runs are not text boxes.',
            ],
        }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('pptx', type=Path)
    parser.add_argument('--output', type=Path, help='Optional JSON report; never the input PPTX')
    args = parser.parse_args()
    try:
        overwrites_input = args.output and (
            args.output.resolve() == args.pptx.resolve()
            or (args.output.exists() and args.output.samefile(args.pptx)))
    except OSError as exc:
        parser.error(f'Cannot check output destination: {exc}')
    if overwrites_input:
        parser.error('--output must not overwrite the input PPTX')
    try:
        report = json.dumps(inspect(args.pptx), ensure_ascii=False, indent=2)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(report + '\n', encoding='utf-8')
        print(report)
    except (OSError, BadZipFile, KeyError, ET.ParseError, ValueError, AttributeError) as exc:
        parser.exit(1, f'Cannot inspect PPTX: {exc}\n')


if __name__ == '__main__':
    main()
