__author__ = ['Pei Kaiyu', 'Chenlong']
__version__ = 'v2.0'

import os
import json
from datetime import datetime
from pdfminer.high_level import extract_pages
from pdfminer.layout import LTTextContainer, LTPage
from data_connector.base_connector import BaseConnector
from utils.pdf_helper.doc_helper import get_name_from_cover, get_date_from_context, get_page_number, \
    remove_legal_disclaimer, get_page_number_from_title, get_header_and_text
from utils.pdf_helper.text_helper import remove_subtext, remove_hyphenation, concat_lines, clean_text
from settings import JB_LEGAL_DISCLAIMER


class RWConnector(BaseConnector):
    doc_type = 'RESEARCH_WEEKLY_SERIES'
    content = 'CONTENT'
    editorial = 'EDITORIAL'
    key_date = 'KEY DATES'
    story = 'STORIES OF THE WEEK'
    invest_idea = 'INVESTMENT IDEAS'
    key_date2 = 'Key dates'
    next_gen = 'NEXT GENERATION'
    big_pic = 'THE BIG PICTURE'
    ecb = 'ECONOMIC BASELINE SCENARIO'
    economy = 'THE ECONOMY'
    capt_market = 'CAPITAL MARKETS'
    ecb_x_px = 60
    footnote = 'MARKET OUTLOOK  For more information, please visit: http://www.juliusbaer.com/ marketoutlook'
    story_left_px = 100
    long_text = 350

    @classmethod
    def get_json_all(cls, fp: str):
        pages = list(extract_pages(fp))
        json_list = []
        front_page = [element for element in pages[0] if isinstance(element, LTTextContainer)]

        # publication_date = get_publication_date(cls.RESEARCH_WEEKLY_SERIES, os.path.basename(filename))
        pub_date = get_date_from_context(front_page[0])
        doc_name = get_name_from_cover(cls.doc_type, pages[0])

        json_list += cls.get_front_page(front_page, pub_date, doc_name)
        json_list += cls.get_story_page(pages, pub_date, doc_name)
        json_list += cls.get_investment_ideas_page(pages, pub_date, doc_name)
        json_list += cls.big_picture_and_ebc_page(pages, pub_date, doc_name)
        return json_list

    @classmethod
    def get_front_page(cls, front_page: list[LTTextContainer], pub_date: str, doc_name: str) -> list[dict]:
        page_num = get_page_number(front_page[1])
        front_page_text = ' '.join([text.get_text() for text in front_page])
        front_page_text = remove_subtext(front_page_text, 'RESEARCH WEEKLY')
        front_page_text = remove_subtext(front_page_text, doc_name.upper())
        front_page_text = remove_legal_disclaimer(front_page_text, JB_LEGAL_DISCLAIMER)
        front_page_text = remove_hyphenation(front_page_text)

        content_beg = front_page_text.index(cls.content)
        editorial_beg = front_page_text.index(cls.editorial)
        try:
            key_date_beg = front_page_text.index(cls.key_date)
        except:
            key_date_beg = front_page_text.index(cls.key_date2)

        content_sec = concat_lines(front_page_text[content_beg: editorial_beg])
        content_sec = remove_subtext(content_sec, cls.content)
        content_sec = remove_subtext(content_sec, cls.footnote)

        editorial_sec = concat_lines(front_page_text[editorial_beg:key_date_beg])
        editorial_sec = remove_subtext(editorial_sec, cls.editorial)

        key_date_sec = concat_lines(front_page_text[key_date_beg:])
        key_date_sec = remove_subtext(key_date_sec, cls.key_date)
        key_date_sec = remove_subtext(key_date_sec, cls.key_date2)

        src_doc = f"Research Weekly {pub_date}"
        content_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num, doc_name=doc_name,
                                          sec_title=cls.content, series='Research Weekly', sec_text=content_sec)
        editorial_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num, doc_name=doc_name,
                                            sec_title=cls.editorial, series='Research Weekly', sec_text=editorial_sec)
        key_date_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num, doc_name=doc_name,
                                           sec_title=cls.key_date, series='Research Weekly', sec_text=key_date_sec)
        section_list = [content_json, editorial_json, key_date_json]
        return section_list

    @classmethod
    def get_story_page(cls, pages: list[LTPage], pub_date: str, doc_name: str) -> list[dict]:
        story_beg = get_page_number_from_title(pages, cls.story)
        story_end = get_page_number_from_title(pages, cls.invest_idea)
        src_doc = f"Research Weekly {pub_date}"
        section_list = []
        for page in pages[story_beg: story_end]:
            left_story, right_story = [], []
            left_story_header, right_story_header = [], []

            for element in list(page)[2:]:
                if not isinstance(element, LTTextContainer):
                    continue

                if element.get_text().startswith(cls.story):
                    continue

                cur_header = left_story_header if element.x0 < cls.story_left_px else right_story_header
                cur_story = left_story if element.x0 < cls.story_left_px else right_story
                if len(cur_header) == 0:
                    story_header, story_text = get_header_and_text(element)
                    cur_header.append(story_header)
                    if story_text != '':
                        cur_story.append(story_text)
                    continue
                cur_story.append(element.get_text())

            page_num = get_page_number(list(page)[1])

            if len(left_story) > 0 and ''.join(left_story).split():
                left_story_text = clean_text(left_story)
                left_story_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num, doc_name=doc_name,
                                                     sec_title=cls.story, series='Research Weekly', sec_text=left_story_text,
                                                     sec_header=left_story_header[0])
                section_list.append(left_story_json)

            if len(right_story) > 0 and ''.join(right_story).split():
                right_story_text = clean_text(right_story)
                right_story_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num, doc_name=doc_name,
                                                      sec_title=cls.story, series='Research Weekly', sec_text=right_story_text,
                                                      sec_header=right_story_header[0])
                section_list.append(right_story_json)
        return section_list

    @classmethod
    def get_investment_ideas_page(cls, pages: list[LTPage], pub_date: str, doc_name: str) -> list[dict]:
        section_list = []
        src_doc = f"Research Weekly {pub_date}"
        invest_idea_beg = get_page_number_from_title(pages, cls.invest_idea)
        invest_idea_end = get_page_number_from_title(pages, cls.next_gen)

        for page in pages[invest_idea_beg:invest_idea_end]:
            page_num = get_page_number(list(page)[1])
            for element in page:
                if not (isinstance(element, LTTextContainer) and len(element.get_text()) > cls.long_text):
                    continue

                section_header, section_text = get_header_and_text(element)
                section_text = remove_hyphenation(section_text)
                section_text = concat_lines(section_text)

                invest_idea_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num,
                                                      doc_name=doc_name, sec_title=cls.invest_idea,
                                                      series='Research Weekly', sec_text=section_text,
                                                      sec_header=section_header)
                section_list.append(invest_idea_json)
        return section_list

    @classmethod
    def big_picture_and_ebc_page(cls, pages: list[LTPage], pub_date: str, doc_name: str) -> list[dict]:
        page_num = get_page_number_from_title(pages, cls.big_pic)
        src_doc = f"Research Weekly {pub_date}"
        economy_list, capt_market_list, ecb_list = [], [], []
        is_ecb = False
        ebc_y_px = cls.get_ebc_y_px(pages[page_num])

        for element in list(pages[page_num])[2:]:
            if not isinstance(element, LTTextContainer):
                continue

            if element.get_text().replace('\n', '').strip() in [cls.big_pic, cls.economy, cls.capt_market, cls.ecb]:
                continue

            if element.y0 < ebc_y_px:
                is_ecb = True

            if element.x0 < cls.ecb_x_px:
                if is_ecb:
                    ecb_list.append(element.get_text().replace('\n', ''))
                else:
                    economy_list.append(element.get_text().replace('\n', ''))
            else:
                if not is_ecb:
                    capt_market_list.append(element.get_text().replace('\n', ''))

        economy_text = ''.join(economy_list)
        capt_market_text = ''.join(capt_market_list)
        ecb_text = ''.join(ecb_list)

        economy_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num, doc_name=doc_name,
                                          sec_title=cls.big_pic, series='Research Weekly', sec_text=economy_text,
                                          sec_header=cls.economy)
        capt_market_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num, doc_name=doc_name,
                                              sec_title=cls.big_pic, series='Research Weekly', sec_text=capt_market_text,
                                              sec_header=cls.capt_market)
        ecb_json = cls.format_section(pub_date=pub_date, src_doc=src_doc, pg_num=page_num, doc_name=doc_name,
                                      sec_title=cls.big_pic, series='Research Weekly', sec_text=ecb_text,
                                      sec_header=cls.ecb)
        section_list = [economy_json, capt_market_json, ecb_json]
        return section_list

    @classmethod
    def get_ebc_y_px(cls, page: LTPage):
        for element in list(page)[2:]:
            if element.get_text().replace('\n', '').strip() in [cls.ecb]:
                return element.y0
        return None


def demo():
    research_weekly_files = os.listdir('data_connector/source/pdf/')
    all_sections = []
    for file in research_weekly_files:
        print('Extracting data from file {}'.format(file))

        sections = RWConnector.get_json_all(f'data_connector/source/pdf/research_weekly/{file}')

        print('Extraction for {} completed'.format(file))

        all_sections = all_sections + sections

