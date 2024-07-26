__author__ = ['Pei Kaiyu', 'Chenlong']
__version__ = 'v2.0'


import uuid
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage

from settings import STOP_STRINGS
from utils.pdf_helper.text_helper import get_substr_first_pos, is_non_text, remove_hyphenation, concat_lines, remove_uncommon_utf8, clean_text
from utils.pdf_helper.doc_helper import get_date_from_meta, get_name_from_path


class BaseConnector:
    @classmethod
    def get_json_all(cls, fp):
        pages = list(extract_pages(fp))
        early_stop = False
        json_list = []

        pub_date = get_date_from_meta(fp)
        src_doc = get_name_from_path(fp)
        doc_name = src_doc.split('.')[0]

        for page in pages:
            if early_stop:
                return json_list

            # start_page = page.pageid
            # end_page = start_page
            # page_num = cls.get_page_num(start_page, end_page)
            page_num = page.pageid

            page_text_list = []
            for element in page:
                if isinstance(element, LTTextContainer):
                    section = element.get_text()
                    if not is_non_text(section):
                        page_text_list.append(section)

            sec_text, early_stop = clean_text(page_text_list, remove_stop_str=True)

            sec_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num, doc_name=doc_name, sec_text=sec_text)
            json_list.append(sec_json)
        return json_list

    @classmethod
    def get_page_num(cls, start_pg, end_pg):
        return str(start_pg) + '-' + str(end_pg)

    @classmethod
    def format_section(cls, pub_date, src_doc, pg_num, doc_name, sec_text, **kwargs):
        sec_id = str(uuid.uuid4())
        series = kwargs.get('series', 'BASE')
        sec_title = kwargs.get('sec_title', '')
        sec_header = kwargs.get('sec_header', '')
        sec_cat = kwargs.get('sec_cat', '')

        sec_json = {'id': sec_id,
                    'publication_date': pub_date,
                    'source_document': src_doc,
                    'series': series,
                    'page_number': pg_num,
                    'document_name': doc_name,
                    'section_title': sec_title,
                    'section_header': sec_header,
                    'section_subcategory': sec_cat,
                    'section_text': sec_text}
        return sec_json


def demo():
    fp = './data/test_file.pdf'
    connector = BaseConnector()
    outputs = connector.get_json_all(fp)
    print(outputs)
    return outputs
