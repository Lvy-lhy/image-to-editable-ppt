"""Small OOXML fixtures exercise the inventory, including misleading flattened slides."""

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from inspect_editability import NS, inspect


XMLNS = ' '.join(f'xmlns:{prefix}="{uri}"' for prefix, uri in NS.items())
TEXT = '<p:sp><p:txBody><a:p><a:r><a:t>标题</a:t></a:r><a:r><a:t>文字</a:t></a:r></a:p></p:txBody></p:sp>'


def picture(x=0, y=0, width=1000, height=600, extra='', kind='pic'):
    return f'''<p:{kind}><p:nvPicPr><p:cNvPr id="3" name="test image"/></p:nvPicPr>
    <p:spPr><a:xfrm {extra}><a:off x="{x}" y="{y}"/><a:ext cx="{width}" cy="{height}"/></a:xfrm>
    <a:blipFill><a:blip r:embed="img1"/></a:blipFill></p:spPr></p:{kind}>'''


def fixture(path, bodies):
    ids = ''.join(f'<p:sldId id="{256+i}" r:id="id{i}"/>' for i in range(len(bodies)))
    with ZipFile(path, 'w') as package:
        package.writestr('ppt/presentation.xml', f'<p:presentation {XMLNS}><p:sldIdLst>{ids}</p:sldIdLst><p:sldSz cx="1000" cy="600"/></p:presentation>')
        # Intentionally reverse numeric part names: inspect must use presentation order.
        rels = ''.join(f'<Relationship Id="id{i}" Target="/ppt/slides/slide{10-i}.xml"/>' for i in range(len(bodies)))
        package.writestr('ppt/_rels/presentation.xml.rels', f'<Relationships>{rels}</Relationships>')
        for i, body in enumerate(bodies):
            package.writestr(f'ppt/slides/slide{10-i}.xml', f'<p:sld {XMLNS}><p:cSld><p:spTree>{body}</p:spTree></p:cSld></p:sld>')


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'fixture.pptx'

    def slide(self, body):
        fixture(self.path, [body])
        return inspect(self.path)['slides'][0]

    def test_native_types_and_text_boxes_not_runs(self):
        report = self.slide(TEXT + '<p:sp/>' + '<p:cxnSp/>' + picture(width=100) + '''
        <p:graphicFrame><a:graphic><a:graphicData><a:tbl><a:tr><a:tc/><a:tc/></a:tr></a:tbl></a:graphicData></a:graphic></p:graphicFrame>
        <p:graphicFrame><c:chart/></p:graphicFrame>''')
        self.assertEqual(report['native_text_boxes'], 1)
        self.assertEqual(report['native_text_characters'], 4)
        self.assertEqual(report['native_shape_objects'], 2)
        self.assertEqual(report['connectors'], 1)
        self.assertEqual(report['picture_objects'], 1)
        self.assertEqual(report['native_tables'], 1)
        self.assertEqual(report['native_charts'], 1)
        self.assertEqual(report['table_cells'], 2)

    def test_full_page_screenshot_with_overlay_is_flagged(self):
        report = self.slide(TEXT + picture())
        self.assertEqual(report['native_text_boxes'], 1)
        self.assertEqual(report['page_covering_image_candidates'][0]['visible_page_coverage'], 1)

    def test_shape_image_fill_and_visible_intersection(self):
        report = self.slide(picture(kind='sp') + picture(x=900))
        self.assertEqual(report['image_filled_shapes'], 1)
        self.assertEqual(len(report['page_covering_image_candidates']), 1)

    def test_nested_group_coordinate_transform(self):
        group = '''<p:grpSp><p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="1000" cy="600"/>
        <a:chOff x="10" y="20"/><a:chExt cx="100" cy="60"/></a:xfrm></p:grpSpPr>'''
        report = self.slide(group + '<p:grpSp>' + picture(10, 20, 100, 60) + '</p:grpSp></p:grpSp>')
        self.assertEqual(report['groups'], 2)
        self.assertEqual(report['page_covering_image_candidates'][0]['visible_page_coverage'], 1)

    def test_rotation_requires_review_and_link_is_reported(self):
        report = self.slide(picture(extra='rot="5400000"').replace('r:embed="img1"', 'r:link="external1"'))
        self.assertEqual(len(report['unmeasured_images']), 1)
        self.assertEqual(report['linked_image_references'], 1)
        self.assertEqual(report['page_covering_image_candidates'], [])

    def test_slide_order_from_relationships(self):
        fixture(self.path, [TEXT, picture()])
        report = inspect(self.path)
        self.assertEqual(report['slide_count'], 2)
        self.assertEqual(report['slides'][0]['native_text_boxes'], 1)
        self.assertEqual(report['slides'][1]['native_text_boxes'], 0)

    def test_cli_refuses_overwriting_input(self):
        fixture(self.path, [TEXT])
        original = self.path.read_bytes()
        process = subprocess.run([sys.executable, str(Path(__file__).with_name('inspect_editability.py')),
                                  str(self.path), '--output', str(self.path)], capture_output=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(self.path.read_bytes(), original)

    def test_cli_refuses_hardlink_to_input(self):
        fixture(self.path, [TEXT])
        original = self.path.read_bytes()
        destination = self.path.with_name('report.json')
        try:
            destination.hardlink_to(self.path)
        except OSError as exc:
            self.skipTest(f'Hardlinks unavailable: {exc}')
        process = subprocess.run([sys.executable, str(Path(__file__).with_name('inspect_editability.py')),
                                  str(self.path), '--output', str(destination)], capture_output=True)
        self.assertNotEqual(process.returncode, 0)
        self.assertEqual(self.path.read_bytes(), original)


if __name__ == '__main__':
    unittest.main()
