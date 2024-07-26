import pdfminer
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.layout import LTTextContainer, LTPage
from datetime import datetime
from utils.pdf_helper.text_helper import concat_lines, get_char_colors


def get_date_from_meta(fp: str) -> str:
    with open(fp, 'rb') as file:
        parser = PDFParser(file)
        docs = PDFDocument(parser)
        metadata = docs.info[0]
        if metadata.get('CreationDate'):
            creation_date = metadata['CreationDate'].decode('utf-8')
            creation_date = creation_date[2:].replace("'", "")
            dt = datetime.strptime(creation_date, "%Y%m%d%H%M%S%z")
            creation_date = dt.strftime("%Y-%m-%d")
            return creation_date
    return ""


def get_date_from_name(name, non_date_str):
    return name.replace(non_date_str, '').replace('.pdf', '').strip()


def get_date_from_header(header_page: LTPage):
    date_header = list(header_page)[0].get_text()
    date_time = date_header.split(',')[1]
    date = date_time.split(';')[0].strip()
    return datetime.strptime(date, '%d %B %Y').strftime('%Y-%m-%d')


def get_date_from_context(element: LTTextContainer) -> str:
    # 'MONDAY, 13 MARCH 2023; 17:00 CET  \n'
    # Convert to datetime object
    input_date_str = element.get_text().split(';')[0].split(',')[1].strip()
    input_date = datetime.strptime(input_date_str, "%d %B %Y")

    # Format the datetime object to ISO format
    iso_format_date = input_date.strftime("%Y-%m-%d")
    return iso_format_date


def get_name_from_path(fp: str) -> str:
    name = fp.split('/')[-1].split('.')[0].strip() + '.pdf'
    return name


def get_name_from_cover(doc_type: str, cover_page: LTPage, is_all_cap_title=True) -> str:
    sub_title = "{} \n".format(doc_type.upper() if is_all_cap_title else doc_type)
    found_name = False
    for element in cover_page:
        if not isinstance(element, LTTextContainer):
            continue

        if found_name:
            return concat_lines(element.get_text())

        if element.get_text().startswith(sub_title):
            document_name = concat_lines(element.get_text().replace(sub_title, ''))
            if document_name:
                return document_name
            else:
                found_name = True
    return ''


def remove_legal_disclaimer(text: str, legal_str: str) -> str:
    return text.replace(legal_str, '')


def get_page_number(element: LTTextContainer) -> int:
    return int(element.get_text().split('/')[0])


def get_page_number_from_title(pages: list, title: str) -> int:
    for page_number, page in enumerate(pages, start=0):
        for element in page:
            if isinstance(element, LTTextContainer) and (title in element.get_text()):
                return page_number
    return 0


def get_header_and_text(element: LTTextContainer):
    header = element.get_text().split('\n')[0]
    text = ''.join(element.get_text().split('\n')[1:])
    return header, text


def get_name_from_color(front_page: LTPage) -> str:
    for element in list(front_page)[2:]:
        if isinstance(element, LTTextContainer) and get_char_colors(element) == {'DeviceRGB'}:
            return element.get_text()
    return ''
