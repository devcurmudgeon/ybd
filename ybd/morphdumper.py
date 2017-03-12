# Copyright (C) 2017  Codethink Limited
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 of the License.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# =*= License: GPL-2 =*=
import yaml
from yaml.representer import SafeRepresenter


def morph_dump(data, defaults):
    """Dumps consistent YAML

    This serialization ensures utf8 encoding where needed, ensures
    that multiline strings are never escaped but nicely output and
    ensures a consistent output order dictated by ybd's defaults.conf.

    Args:
        data: The data to dump
        default: A Defaults object

    Returns:
        The data ready to write to a file
    """
    class MorphDumper(yaml.SafeDumper):

        # Output in the order dictated by defaults.conf
        keyorder = defaults.fields + defaults.build_steps

        def __init__(self, *args, **kwargs):

            yaml.SafeDumper.__init__(self, *args, **kwargs)

            # Ensure consistently ordered output
            self.add_representer(dict, self._represent_dict)

            # Use simple notation for one line strings, and
            # use '|' notation for multiline text, never stringify
            # and excape newlines.
            self.add_representer(str, self._represent_str)
            self.add_representer(unicode, self._represent_unicode)

        # Never emit aliases
        #
        # copied from http://stackoverflow.com/questions/21016220
        def ignore_aliases(self, data):
            return True

        def _iter_in_global_order(cls, mapping):
            for key in cls.keyorder:
                if key in mapping:
                    yield key, mapping[key]
            for key in sorted(mapping.iterkeys()):
                if key not in cls.keyorder:
                    yield key, mapping[key]

        def _represent_dict(cls, dumper, mapping):
            return dumper.represent_mapping('tag:yaml.org,2002:map',
                                            cls._iter_in_global_order(mapping))

        def _represent_str(cls, dumper, orig_data):
            try:
                data = unicode(orig_data, 'ascii')
                if data.count('\n') == 0:
                    return SafeRepresenter.represent_str(dumper, orig_data)
            except UnicodeDecodeError:
                try:
                    data = unicode(orig_data, 'utf-8')
                    if data.count('\n') == 0:
                        return SafeRepresenter.represent_str(dumper, orig_data)
                except UnicodeDecodeError:
                    return SafeRepresenter.represent_str(dumper, orig_data)
            return dumper.represent_scalar(u'tag:yaml.org,2002:str',
                                           data, style='|')

        def _represent_unicode(cls, dumper, data):
            if data.count('\n') == 0:
                return SafeRepresenter.represent_unicode(dumper, data)
            return dumper.represent_scalar(u'tag:yaml.org,2002:str',
                                           data, style='|')

    return yaml.dump(data,
                     default_flow_style=False,
                     encoding='utf-8',
                     line_break="\n",
                     Dumper=MorphDumper)
