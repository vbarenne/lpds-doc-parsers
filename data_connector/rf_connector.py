__author__ = ['Pei Kaiyu', 'Alvin']
__version__ = 'v2.0'


import os
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage
from data_connector.base_connector import BaseConnector
from utils.pdf_helper.doc_helper import get_page_number_from_title, get_date_from_context, get_name_from_color
from utils.pdf_helper.text_helper import is_header_match, remove_hyphenation, concat_lines, remove_uncommon_utf8


class RFConnector(BaseConnector):
    doc_type = 'Research Focus'
    legal_info = 'IMPORTANT LEGAL INFORMATION'
    small_text = 30
    table_element = 100
    valid_content = 1000
    overlap = 150

    @classmethod
    def get_json_all(cls, fp: str):
        pages = list(extract_pages(fp))
        front_page = [element for element in pages[0] if isinstance(element, LTTextContainer)]
        json_list = []

        pub_date = get_date_from_context(front_page[0])
        doc_name = get_name_from_color(pages[0])
        src_doc = "{} {}".format(cls.doc_type, pub_date)

        legal_page = get_page_number_from_title(pages, cls.legal_info) - 1
        pages = pages[:legal_page]

        for page_num, page in enumerate(pages, start=1):
            is_table_page = cls.is_table_page(page)
            if is_table_page:
                continue

            sections = cls.get_sections(page)

            for sec_text in sections:
                sec_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num, doc_name=doc_name,
                                              sec_title='', sec_header='', sec_text=sec_text, series=cls.doc_type)
                json_list.append(sec_json)

        return json_list

    @classmethod
    def is_table_page(cls, page: LTPage):
        element_num = 0
        for element in page:
            if isinstance(element, LTTextContainer) and len(element.get_text()) < cls.small_text:
                element_num += 1

        if element_num >= cls.table_element:
            return True
        return False

    @classmethod
    def get_sections(cls, page: LTPage) -> list[dict]:
        sections = []
        section_text = ''

        for element in page:
            if isinstance(element, LTTextContainer) and cls.is_content(element):
                section_text = section_text + element.get_text()

            section_text = cls.clean_text(section_text)
            if len(section_text) >= cls.valid_content:
                sections.append(section_text)
                section_text = ''

        if len(section_text) > 0:
            sections.append(section_text)

        sections = cls.get_overlap(sections)
        return sections

    @classmethod
    def get_overlap(cls, str_list):
        for i in range(1, len(str_list) - 1):
            next_sec = str_list[i + 1]
            cur_sec = str_list[i]
            str_list[i] = cur_sec + next_sec[0: cls.overlap]
        return str_list

    @classmethod
    def is_content(cls, element):
        is_large_text = len(element.get_text()) > 10
        is_disclaimer = '|' in element.get_text()
        is_source = ('Source:' in element.get_text()) or is_header_match(element, 'Source:', 'Source')
        is_contact = '@juliusbaer.com' in element.get_text()
        is_exhibit = 'Exhibit' in element.get_text()

        is_content = is_large_text and (not is_disclaimer) and (not is_source) and (not is_contact) and (not is_exhibit)
        return is_content

    @classmethod
    def clean_text(cls, text):
        text = remove_hyphenation(text)
        text = concat_lines(text)
        text = remove_uncommon_utf8(text)
        return text
