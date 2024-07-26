__author__ = ['Pei Kaiyu', 'Chenlong']
__version__ = 'v2.0'


import os
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage, LTTextBoxHorizontal
from data_connector.base_connector import BaseConnector
from utils.pdf_helper.doc_helper import get_date_from_name, get_name_from_cover
from utils.pdf_helper.text_helper import is_header_match, remove_footer, get_char_colors, remove_hyphenation, concat_lines, remove_uncommon_utf8, clean_text


class CIOConnector(BaseConnector):
    doc_type = 'CIO Weekly'
    contact_page = 'Contact \n'
    left_sec_x0 = 250
    page_start = 2
    
    @classmethod
    def get_json_all(cls, fp):
        pages = list(extract_pages(fp))
        json_list = []

        pub_date = get_date_from_name(os.path.basename(fp), cls.doc_type)
        doc_name = get_name_from_cover(cls.doc_type, pages[0], is_all_cap_title=False)
        is_sec_element = False
        page_num = 0
        cur_section = []
        cur_header = ''

        for page in pages:
            elements, is_last_page, is_sec_element = cls.get_page_elements(page, is_sec_element)
            sections, cur_header, cur_section = cls.get_sections(elements, cur_header=cur_header, cur_section=cur_section)
            page_num += 1
            for sec_header, sec_text in sections:
                sec_json = cls.format_section(pub_date=pub_date, src_doc="CIO Weekly {}".format(pub_date), pg_num=page_num, doc_name=doc_name, sec_title=doc_name, sec_header=sec_header, sec_text=sec_text, series="CIO Weekly")
                json_list.append(sec_json)

            if is_last_page:
                break
        
        if len(cur_section) > 0:
            sec_text = clean_text(cur_section)
            sec_json = cls.format_section(pub_date=pub_date, src_doc="CIO Weekly {}".format(pub_date), pg_num=page_num, doc_name=doc_name, sec_title=doc_name, sec_header=cur_header, sec_text=sec_text, series="CIO Weekly")
            json_list.append(sec_json)
        return json_list

    @classmethod
    def get_page_elements(cls, page, is_sec_element):
        left_elements, right_elements = [], []
        is_last_page = False

        for element in list(page)[cls.page_start:]:
            if isinstance(element, LTTextContainer) and cls.contact_page in element.get_text():
                is_last_page = True
                if element.x0 < cls.left_sec_x0:
                    break
            
            if not isinstance(element, LTTextBoxHorizontal):
                continue

            if not is_sec_element:
                is_sec_element = is_header_match(element, 'Source:', 'Source') or is_header_match(element, 'Note:', 'Note')
                continue

            if element.x0 < cls.left_sec_x0:
                left_elements.append(element)
            elif not is_last_page:
                right_elements.append(element)

        left_elements = remove_footer(left_elements)
        right_elements = remove_footer(right_elements)
        elements = left_elements + right_elements
        return elements, is_last_page, is_sec_element

    @classmethod
    def get_sections(cls, elements, **kwargs):
        cur_header = kwargs.get('cur_header', '')
        cur_section = kwargs.get('cur_section', [])
        sections = []
        for element in elements:
            if "DeviceRGB" not in get_char_colors(element):
                cur_section.append(element.get_text())
                continue

            if len(cur_section) > 0:
                sections.append([cur_header, clean_text(cur_section)])
                cur_section = []

            cur_header, cur_text = cls.get_header_text(element)
            cur_section.append(cur_text)
        return sections, cur_header, cur_section

    @classmethod
    def get_header_text(cls, element: LTTextBoxHorizontal):
        header_list = []
        text_list = []
        for i in range(1, len(element)+1):
            if get_char_colors(list(element)[0:i]) == {'DeviceRGB'}:
                header_list.append(list(element)[i-1].get_text())
            else:
                text_list.append(list(element)[i-1].get_text())

        header = concat_lines(''.join(header_list))
        text = clean_text(text_list)
        return header, text
    
