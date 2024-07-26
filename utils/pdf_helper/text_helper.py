from typing import List
from pdfminer.layout import LTTextContainer, LTChar, LTTextLineHorizontal, LTTextBoxHorizontal
import unicodedata, re
from settings import FOOTER_FONT, STOP_STRINGS


class Trie:
    def __init__(self):
        self.children = {}
        self.is_end = False

    def builder(self, str_list):
        root = Trie()
        for string in str_list:
            cur_node = root
            for char in string:
                if char not in cur_node.children:
                    cur_node.children[char] = Trie()
                cur_node = cur_node.children[char]
            cur_node.is_end = True
        return root

    def retriever(self, query, root):
        cur_node = root
        for char in query:
            if char not in cur_node.children:
                return False
            cur_node = cur_node.children[char]
            if cur_node.is_end:
                return True
        return False


def concat_lines(text: str) -> str:
    return text.replace('\n', '')


def remove_hyphenation(text: str) -> str:
    return text.replace('-\n', '')


def is_non_text(text):
    pattern = r'^[0-9\s!"#$%&\'()*+,-./:;<=>?@\[\\\]^_`{|}~]*$'
    match = re.match(pattern, text)
    return match is not None


def remove_uncommon_utf8(text) -> str:
    filtered_text = ""
    for char in text:
        if unicodedata.category(char)[0] == 'C':
            continue
        filtered_text += char
    return filtered_text


def get_substr_first_pos(query, str_list):
    trie = Trie()
    root = trie.builder(str_list)
    for i in range(len(query)):
        if trie.retriever(query[i:], root):
            return i
    return None


def remove_subtext(text, rm_text):
    return text.replace(rm_text, '')


def is_header_match(element: LTTextContainer, header_text: str, bold_text: str) -> bool:
    if len(element) > 0:
        first_text_line = list(element)[0]
        if first_text_line.get_text().startswith(header_text):
            return is_text_in_bold(first_text_line, bold_text)
    return False


def is_footer(element: LTTextBoxHorizontal) -> bool:
    for text_line in element:
        for character in text_line:
            if isinstance(character, LTChar) and character.get_text().strip():
                if int(character.size) > FOOTER_FONT:
                    return False
    return True


def remove_footer(elements: list[LTTextBoxHorizontal]) -> list[LTTextBoxHorizontal]:
    while len(elements) > 0 and is_footer(elements[-1]):
        elements.pop()
    return elements


def get_char_colors(element: LTTextContainer) -> set[str]:
    color_space_set = set()
    for text_line in element:
        for character in text_line:
            if not isinstance(character, LTChar):
                continue

            if character.ncs.name not in color_space_set:
                color_space_set.add(character.ncs.name)
            break
    return color_space_set


def clean_text(text_list, remove_stop_str=False):
    text = ''.join(text_list)
    text = remove_hyphenation(text)
    text = concat_lines(text)
    text = remove_uncommon_utf8(text)

    if not remove_stop_str:
        return text

    early_stop = False
    rm_start_pos = get_substr_first_pos(text, STOP_STRINGS)
    if rm_start_pos is not None:
        early_stop = True
        text = text[:rm_start_pos]
    return text, early_stop


def is_text_in_font_size(elements: list, font_size: int) -> bool:
    for character in elements:
        if isinstance(character, LTChar) and int(character.size) != font_size:
            return False
    return True


def is_text_in_bold(element: LTTextLineHorizontal, text: str) -> bool:
    for character in list(element)[0:len(text)]:
        if isinstance(character, LTChar):
            if not character.fontname.endswith('Bold'):
                return False
    return True


def is_within_rectangles(element, rects):
    for rect in rects:
        if (element.x0 >= rect.x0 and element.x1 <= rect.x1 and
                element.y0 >= rect.y0 and element.y1 <= rect.y1):
            return True
    return False


def get_colors(element: LTTextContainer) -> set[str]:
    colors_set = set()
    for text_line in element:
        for character in text_line:
            if not isinstance(character, LTChar):
                continue
            if character.graphicstate.ncolor not in colors_set:
                colors_set.add(character.graphicstate.ncolor)
            break
    return colors_set

def get_jb_rating(txt):
    if "buy" in txt.lower():
        return "Buy"
    if "hold" in txt.lower():
        return "Hold"
    if "sell" in txt.lower():
        return "Sell"






