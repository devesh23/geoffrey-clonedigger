import os
import logging
import asyncio
import tempfile
from html import parser
from xml.etree import ElementTree

from geoffrey import plugin
from geoffrey.data import EventType
from geoffrey.utils import execute
from geoffrey.subscription import subscription


class HTMLParser(parser.HTMLParser):
    """ Basic parser for CloneDigger html output """

    def __init__(self, *args, **kwargs):
        """ initialize necessary variables """
        super().__init__(*args, **kwargs)
        self.read_data = False
        self.tagread = 0
        self.current_tag = None
        self.tag_data = {}

    def handle_starttag(self, tag, attrs):
        """ do stuff when start tag has been found """
        if tag == 'p':
            self.read_data = True
            self.current_tag = 'p'
            self.tagread += 1

    def handle_endtag(self, tag):
        """ do stuff when end tag has been found """
        if tag == self.current_tag:
            self.read_data = False

    def handle_data(self, data):
        """ do stuff when data has been found """
        if self.read_data == True:
            if self.current_tag + str(self.tagread) in self.tag_data:
                self.tag_data[self.current_tag + str(self.tagread)] += data
            else:
                self.tag_data[self.current_tag + str(self.tagread)] = data


class CloneDigger(plugin.GeoffreyPlugin):
    """
    clonedigger plugin.

    """
    @subscription
    def modified_files(self, event):
        """
        Subscription criteria.

        Should be used as annotation of plugin.Tasks arguments.
        Can be used multiple times.

        """
        return (self.project.name == event.project and
                event.plugin == "filecontent" and
                event.key.endswith('.py') and
                event.type in (EventType.created, EventType.modified))

    @asyncio.coroutine
    def run_clonedigger(self, events:"modified_files") -> plugin.Task:
        """
        Main plugin task.

        Process `events` of the subscription `modified_files` and put
        states or events to the hub.

        """

        clonedigger_path = self.config.get(self._section_name, "clonedigger_path")

        while True:
            event = yield from events.get()
            filename = event.key

            self.log.critical("Event received in plugin `clonedigger`")

            with tempfile.TemporaryDirectory() as td:
                execution_stats = yield from execute(clonedigger_path, '--cpd-output', filename, cwd=td)
                computed_path = os.path.join(td, 'output.xml')
#                html_output = open(os.path.join(td, 'output.html')).read()
                if not os.path.exists(computed_path):
                    self.log.warning('Clonedigger did not generate output file')
                    continue
                else:
                    xml_output = open(computed_path, 'rb').read()

            data = {}
            
#            html_data = self.parse_html(html_output)
            xml_data = self.parse_xml(xml_output)

#            data['html'] = html_data
            data['xml'] = xml_data

            state = self.new_state(key=filename, **data)
            yield from self.hub.put(state)

    def parse_html(self, html):
        """ Parse HTML output """
        parser = HTMLParser()
        parser.feed(html)
        return parser.tag_data

    def parse_xml(self, xml):
        """ Parse XML output """

        etree = ElementTree.fromstring(xml)
        parsed_data = []
        for iteration, dup_item in enumerate(etree.findall('duplication')):

            dup_stats = dup_item.items()
            data = { key: int(value) for key,value in dup_item.items() }
            files = []
            for element in dup_item.getchildren():
                if element.tag == 'file':
                    element_data = {} 
                    for key, value in element.items():
                        if value.isnumeric():
                            element_data[key] = int(value)               
                        else:
                            element_data[key] = value


                    files.append(element_data)
                elif element.tag == 'codefragment':
                    codefragment = element
            
            data.update({'files': files})
            data.update({'codefragment': codefragment.text})
            parsed_data.append(data)

        return parsed_data
