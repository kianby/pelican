#!/usr/bin/env python
# -*- coding: utf-8 -*- #

"""
    PluXmL2Pelican

    Import PluXmL blog into Pelican

    @copyright: 2013 by Yax <kianby@gmail.com>
    @license: GNU GPL, see COPYING for details.
"""

import os
import re
import logging
import textwrap
import argparse
from codecs import open
from bs4 import BeautifulSoup
from bs4 import NavigableString
from bs4 import Tag


# configure logging
logging.basicConfig(level=logging.INFO)


def toUnicode(value):
    if type(value) is not unicode:
        value = unicode(value, errors='replace')
    return value.encode('utf-8')


def removeMultipleSpaces(text):
    index = text.find('  ')
    while index != -1:
        text = text.replace('  ', ' ')
        index = text.find('  ')
    return text


def normalizedText(text):
    text = text.strip()
    for substring in ['\n', '\r', '&nbsp;']:
        text = text.replace(substring, ' ')
    return removeMultipleSpaces(text)


def normalizedBlock(block):
    block = block.replace(' .', '.').replace(
        '[ ', '[').replace(' ,', ',')
    block = textwrap.fill(removeMultipleSpaces(block), 80)
    lines = []
    line_number = 0
    for line in block.split('\n'):
        if line[:1] == ':' and line_number > 0:
            if lines[line_number - 1][-1:] == ' ':
                lines[line_number - 1] = lines[line_number - 1] + ':'
            else:
                lines[line_number - 1] = lines[line_number - 1] + ' :'
            line = line[1:]
        lines.append(line)
        line_number = line_number + 1
    return "\n".join(lines)


class HtmlElement(object):

    def __init__(self, value=''):
        self.value = value

    def getValue(self):
        return self.value


class HtmlParagraph(HtmlElement):
    pass


class HtmlText(HtmlElement):
    pass


class HtmlTextStart(HtmlElement):

    def setAttribute(self, attribute):
        self.attribute = attribute

    def getAttribute(self):
        return self.attribute


class HtmlTextEnd(HtmlElement):
    pass


class HtmlLinkStart(HtmlElement):
    pass


class HtmlLinkEnd(HtmlElement):
    pass


class HtmlImage(HtmlElement):
    pass


class HtmlPre(HtmlElement):
    pass


class HtmlListStart(HtmlElement):
    pass


class HtmlListEnd(HtmlElement):
    pass


class MarkdownArticle(object):

    def __init__(self):
        self.document = []

    def parse(self, article):
        soup = BeautifulSoup(article)
        body = soup.find('body')
        if not body:
            body = soup
        for element in body.contents:
            self.parse_element(element)

    def parse_element(self, element):
        logging.debug('write element %s' % (type(element)))
        if type(element) is NavigableString:
            self.document.append(HtmlText(element.string.encode("UTF-8")))
        elif type(element) is Tag:
            logging.debug('tag %s ' % element.name)
            if element.name == 'br':
                self.document.append(HtmlParagraph())
            elif element.name == 'p':
                self.document.append(HtmlParagraph())
                for content in element.contents:
                    self.parse_element(content)
                self.document.append(HtmlParagraph())
            elif element.name == 'a':
                if 'href' in element.attrs:
                    self.document.append(HtmlLinkStart())
                    href_link = element['href']
                    if href_link and href_link[:5] == 'data/':
                        href_link = 'static/%s' % href_link[5:]
                    for content in element.contents:
                        self.parse_element(content)
                    self.document.append(HtmlLinkEnd(href_link))
                else:
                    logging.warn('unsupported <a> content')
            elif element.name == 'img':
                if 'src' in element.attrs and element['src'][:5] == 'data/':
                    element['src'] = 'static/%s' % element['src'][5:]
                self.document.append(HtmlImage(str(element)))
            elif element.name in ['strong', 'em', 'i', 'b']:
                text_tag = '*' if element.name in ['em', 'i'] else '**'
                text_start = HtmlTextStart()
                text_start.setAttribute(text_tag)
                self.document.append(text_start)
                for content in element.contents:
                    self.parse_element(content)
                self.document.append(HtmlTextEnd())
            elif element.name == 'span':
                text_tag = ''
                if 'style' in element.attrs:
                    if element['style'] == 'font-style: italic;':
                        text_tag = '*'
                    elif element['style'] == 'font-weight: bold;':
                        text_tag = '**'
                    else:
                        logging.warn('unsupported SPAN style %s ' %
                                        element['style'])
                else:
                    logging.warn('unsupported SPAN %s' % element)
                text_start = HtmlTextStart()
                text_start.setAttribute(text_tag)
                self.document.append(text_start)
                for content in element.contents:
                    self.parse_element(content)
                self.document.append(HtmlTextEnd())
            elif element.name == 'pre':
                self.document.append(HtmlParagraph())
                code_block = ''
                for content in element.contents:
                    line_tab = '    '
                    if type(content) is Tag:
                        if content.name in ['br']:
                            continue
                        else:
                            logging.warn('unsupported element in PRE: %s' %
                                    str(content))
                            content = '!TODO! ' + str(content)
                    if content[:4] == '    ':
                        line_tab = ''
                    content = content.encode('UTF-8')
                    for line in content.split('\n'):
                        for substring in ['\n', '\r']:
                            line = line.replace(substring, '')
                        if line[:4] != '    ' and not line_tab:
                            line = '    ' + line
                        code_block = code_block + '%s%s\n' % (line_tab,
                                str(line))
                self.document.append(HtmlPre(code_block))
            elif element.name in ['ul', 'ol']:
                list_prefix = '*' if element.name == 'ul' else '-'
                self.document.append(HtmlListStart(list_prefix))
                for content in element.contents:
                    if type(content) is Tag:
                        if content.name == 'li':
                            li_text = ' '.join([li.string.encode('UTF-8')
                                for li in content.contents
                                    if li and li.string])
                            self.document.append(HtmlText(li_text))
                        elif content.name == 'br':
                            pass
                        else:
                            logging.warn('skip element in ul/ol %s' %
                                content.name)
                    elif type(content) is NavigableString:
                        pass
                    else:
                        logging.warn('unexpected element in ul %s' %
                                type(content))
                self.document.append(HtmlListEnd())
            elif element.name in ['table', 'embed']:
                self.document.append(HtmlText(str(element)))
            else:
                self.document.append(HtmlText('!TODO! %s' %
                    str(element)))
                logging.warn('unsupported tag %s' % element.name)
        else:
            logging.warn('unsupported element type %s ' % type(element))

    def write(self, markdown):
        current_text = ''
        current_style = ''
        current_list = ''
        for element in self.document:
            if type(element) is HtmlText:
                text = normalizedText(element.getValue())
                if current_list:
                    text = '%s    %s' % (current_list, normalizedBlock(text))
                    markdown.write(text)
                    markdown.write('\n')
                else:
                    if current_text and current_text[-1:] not in [' ', '*']:
                        current_text = current_text + ' '
                    current_text = current_text + text
            elif type(element) is HtmlParagraph:
                current_text = normalizedBlock(current_text)
                if current_text:
                    markdown.write(current_text)
                    markdown.write('\n\n')
                current_text = ''
            elif type(element) is HtmlTextStart:
                current_text = current_text + ' ' + element.getAttribute()
                current_style = element.getAttribute()
            elif type(element) is HtmlTextEnd:
                current_text = current_text + current_style + ' '
                current_style = ''
            elif type(element) is HtmlLinkStart:
                current_text = current_text + ' ['
            elif type(element) is HtmlLinkEnd:
                current_text = "%s](%s)" % (current_text,
                        toUnicode(element.getValue()))
            elif type(element) is HtmlListStart:
                markdown.write(normalizedBlock(current_text))
                markdown.write('\n\n')
                current_text = ''
                current_list = element.getValue()
            elif type(element) is HtmlListEnd:
                current_list = ''
                markdown.write('\n')
            elif type(element) is HtmlImage:
                current_text = current_text + ' ' + element.getValue() + ' '
            elif type(element) is HtmlPre:
                markdown.write(element.getValue())

        markdown.write('\n')
        markdown.write(normalizedBlock(current_text))


class PluXmL2Pelican(object):
    """Class that converts PluXmL blog to Pelican blog.
    """

    def __init__(self, pluxml_root_path, pelican_root_path):
        self.pluxml_root_path = pluxml_root_path
        self.pelican_root_path = pelican_root_path
        self.pluxml_article_path = "/".join(
            [self.pluxml_root_path, 'data', 'articles'])
        self.pluxml_comment_path = "/".join([
            self.pluxml_root_path, 'data', 'commentaires'])
        self.pluxml_categories_filename = "/".join([
            self.pluxml_root_path, 'data', 'configuration', 'categories.xml'])
        self.pluxml_tags_filename = "/".join([
            self.pluxml_root_path, 'data', 'configuration', 'tags.xml'])
        self.context = []

    def parse_article(self, xml):
        # extract
        # 0008.001,005.001.200912021055.sfr-3g-et-ubuntu-9-10-karmic
        m = re.search('(\d+)\.(.*)\.\d+\.(\d+)\.(.*)\.xml', xml)
        if not m:
            logging.error('cannot split filename to get article attributes')
            return
        numero = m.group(1)
        categories = m.group(2)
        post_date = m.group(3)
        name = m.group(4)
        xmlfile = open(xml, encoding='utf-8').read()
        soup = BeautifulSoup(xmlfile, 'xml')
        title = soup.document.title.contents[0].encode('UTF-8')
        article = soup.document.content.contents[0]

        logging.debug('## No %s Name %s Title %s ' % (numero, name, title))
        logging.debug('##Categories %s Date %s' % (categories, post_date))

        categories = [self.categories[cat] for cat in
                categories.split(',') if cat in self.categories]
        if numero in self.tags:
            categories = categories + self.tags[numero].split(',')
        categories = sorted(categories)

        # create Markdown file
        markdown = open("/".join([self.pelican_root_path, 'content',
                        '%s.%s.md' % (numero, name)]), 'w')

        # create header
        markdown.write('Title: %s\n' % title)
        markdown.write(
            'Date: %s-%s-%s %s:%s\n' % (post_date[0:4], post_date[4:6],
                                        post_date[6:8], post_date[8:10],
                                        post_date[10:12]))
        #markdown.write('Category: %s\n' % categories[0].encode('UTF-8'))
        markdown.write('Tags: %s\n' % ','.join(categories).encode('UTF-8'))
        markdown.write('\n\n')

        # parse HTML
        markdown_article = MarkdownArticle()
        markdown_article.parse(article)

        #for element in markdown_article.document:
        #    print '%s [%s]' % (type(element), element.getValue())

        # write Markdown
        markdown_article.write(markdown)

        markdown.close()

    def parse_categories(self):
        self.categories = {}
        xmlfile = open(self.pluxml_categories_filename,
                encoding='utf-8').read()
        soup = BeautifulSoup(xmlfile, 'xml')
        for cat in soup.findAll('categorie'):
            if 'number' in cat.attrs:
                cat_number = cat['number']
                for element_name in cat.findAll('name'):
                    cat_label = element_name.contents[0]
                    self.categories[cat_number] = cat_label
        #print self.categories

    def parse_tags(self):
        self.tags = {}
        xmlfile = open(self.pluxml_tags_filename, encoding='utf-8').read()
        soup = BeautifulSoup(xmlfile, 'xml')
        for art in soup.findAll('article'):
            if 'number' in art.attrs:
                art_number = art['number']
                tags = art.contents[0].strip()
                if tags:
                    self.tags[art_number] = tags.title()
        #print self.tags

    def launch(self):
        self.parse_categories()
        self.parse_tags()
        for filename in os.listdir(self.pluxml_article_path):
            if filename[-4:] == '.xml':
                logging.info('convert article %s' % filename)
                self.parse_article("/".join(
                    [self.pluxml_article_path, filename]))


def main(from_pluxml_dir, to_pelican_dir):
    converter = PluXmL2Pelican(from_pluxml_dir, to_pelican_dir)
    converter.launch()


if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--version', action='version', version='%(prog)s 1.0')
    p.add_argument('-f', '--from_pluxml', help='from PluXmL root directory',
            required=True)
    p.add_argument('-t', '--to_pelican', help='to Pelican root directory',
            required=True)
    args = p.parse_args()
    main(args.from_pluxml, args.to_pelican)
