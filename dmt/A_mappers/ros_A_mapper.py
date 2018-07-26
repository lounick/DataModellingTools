import re
import os

try:
    from cStringIO import StringIO
except ImportError:
    from io import StringIO

import hashlib
import sys
from typing import Union, List

from ..commonPy import asnParser
from ..commonPy.utility import panic, inform
from ..commonPy.asnAST import (
    AsnBool, AsnInt, AsnReal, AsnString, isSequenceVariable, AsnEnumerated,
    AsnSequence, AsnSet, AsnChoice, AsnMetaMember, AsnSequenceOf, AsnSetOf,
    AsnBasicNode, AsnNode, AsnSequenceOrSet, AsnSequenceOrSetOf,
    AsnAsciiString)
from ..commonPy.asnParser import AST_Lookup, AST_Leaftypes
from ..commonPy.cleanupNodes import SetOfBadTypenames

primitive_types = {
    'T-Boolean': 'bool', 'T-Int8': 'int8', 'T-UInt8': 'uint8',
    'T-Int16': 'int16', 'T-UInt16': 'uint16', 'T-Int32': 'int32',
    'T-UInt32': 'uint32', 'T-Int64': 'int64', 'T-UInt64': 'uint64',
    'T-Float': 'float32', 'T-Double': 'float64', 'T-String': 'string',
    'T-Time': 'time', 'T-Duration': 'duration', 'T-Int8': 'byte',
    'T-UInt8': 'char'}

ans1_simple_types = ['BOOLEAN', 'INTEGER', 'BIT STRING', 'OCTET STRING', 'NULL',
                     'OBJECT IDENTIFIER', 'REAL', 'ENUMERATED',
                     'CHARACTER STRING']

supported_asn1_types = ['BOOLEAN', 'INTEGER', 'OCTET STRING', 'REAL',
                        'ENUMERATED', 'AsciiString', 'NumberString',
                        'VisibleString', 'PrintableString']

# The ROS message header file
g_outputH = None

# The ROS message source file TODO: Is it needed? Messages are templated
g_outputC = None

# The ROS message representation dictionary
g_ros_repr = {}

# Computed md5 hashes
g_md5_hashes = {}

# Computed ROS message text representation
g_msg_text = {}


def Version() -> None:
    print("Code generator: " +
          "$Id: python_A_mapper.py $")  # pragma: no cover


def OnStartup(unused_modelingLanguage: str, asnFile: str, outputDir: str, badTypes: SetOfBadTypenames) -> None:
    # import pprint
    # pprint.pprint('===================================================================')
    # pprint.pprint(asnParser.g_modules)
    # pprint.pprint('-------------------------------------------------------------------')
    # pprint.pprint(asnParser.g_names)
    # pprint.pprint('-------------------------------------------------------------------')
    # pprint.pprint(asnParser.g_leafTypeDict)
    # pprint.pprint('-------------------------------------------------------------------')
    # pprint.pprint(asnParser.g_typesOfFile)
    # pprint.pprint('-------------------------------------------------------------------')
    # pprint.pprint(asnParser.g_astOfFile)
    # pprint.pprint('-------------------------------------------------------------------')
    # pprint.pprint(asnParser.g_typesOfFile[asnFile])
    # pprint.pprint('-------------------------------------------------------------------')
    # pprint.pprint(asnParser.g_astOfFile[asnFile])
    # pprint.pprint('===================================================================')
    if not asnFile.endswith(".asn"):
        panic("The ASN.1 grammar file (%s) doesn't end in .asn" %
              asnFile)  # pragma: no cover

    global g_ros_repr
    # g_ros_repr = {}
    global g_msg_text

    # For each SEQUENCE or SET we need to generate a message header
    # Format a ROS message based on the ASN.1 message
    # TODO (Niko): Even if it is not a SEQUENCE or SET we should generate
    # messages. An interface can accept a single value as data, for example
    # a single UInt32. We should be able to serialise and deserialise this
    # king of message (See for example std_msgs/UInt32.msg)
    for msg in asnParser.g_typesOfFile[asnFile]:
        if (isinstance(asnParser.g_names[msg], AsnSequence) or
                isinstance(asnParser.g_names[msg], AsnSet)):
                g_ros_repr[msg] = process_message(msg)

    # Calculate the MD5
    for msg in asnParser.g_typesOfFile[asnFile]:
        if (isinstance(asnParser.g_names[msg], AsnSequence) or
                isinstance(asnParser.g_names[msg], AsnSet)):
                compute_md5(msg)

    # Generate the header
    for msg in asnParser.g_typesOfFile[asnFile]:
        if (isinstance(asnParser.g_names[msg], AsnSequence) or
                isinstance(asnParser.g_names[msg], AsnSet)):
                module = find_message_module(msg)
                message = Message(msg, module, g_msg_text[msg],
                                  g_md5_hashes[msg])
                output_path = outputDir + os.sep + module
                if not os.path.exists(output_path):
                    os.makedirs(output_path)
                header = open(output_path + "/" + message.name + ".h", "w")
                msg_file = open(output_path + "/" + message.name + ".msg", "w")
                message.make_header(header)
                message.make_msg(msg_file)
                header.close()
                msg_file.close()

def OnBasic(unused_nodeTypename: str, unused_node: AsnBasicNode, unused_leafTypeDict: AST_Leaftypes) -> None:
    pass


def OnSequence(unused_nodeTypename: str, unused_node: AsnSequenceOrSet, unused_leafTypeDict: AST_Leaftypes) -> None:
    pass


def OnSet(unused_nodeTypename: str, unused_node: AsnSequenceOrSet, unused_leafTypeDict: AST_Leaftypes) -> None:
    pass  # pragma: nocover


def OnEnumerated(unused_nodeTypename: str, unused_node: AsnEnumerated, unused_leafTypeDict: AST_Leaftypes) -> None:
    pass


def OnSequenceOf(unused_nodeTypename: str, unused_node: AsnSequenceOrSetOf, unused_leafTypeDict: AST_Leaftypes) -> None:
    pass


def OnSetOf(unused_nodeTypename: str, unused_node: AsnSequenceOrSetOf, unused_leafTypeDict: AST_Leaftypes) -> None:
    pass  # pragma: nocover


def OnChoice(unused_nodeTypename: str, unused_node: AsnChoice, unused_leafTypeDict: AST_Leaftypes) -> None:
    pass


def OnShutdown(unused_badTypes: SetOfBadTypenames) -> None:
    pass

def generate_msg_text(msg: str) -> str:
    global g_msg_text

    if msg in g_msg_text.keys():
        return g_msg_text[msg]

    definition = g_ros_repr[msg]

    buff = StringIO()

    for const in definition['constants']:
        buff.write("%s %s=%s\n" % (const[0], const[1], const[2]))

    for var in definition['variables']:
        buff.write("%s %s\n" % (var[0], var[1]))
    g_msg_text[msg] = buff.getvalue().strip()
    return buff.getvalue().strip()


def compute_md5_from_ast(msg: str) -> str:
    global g_ros_repr
    msg_dict = process_message(remove_module(msg))
    g_ros_repr[msg] = msg_dict
    return compute_md5(msg)


def compute_md5(msg: str) -> str:
    print("Calculating md5 for message: %s" % (msg))

    global g_ros_repr
    global g_md5_hashes

    if msg in g_md5_hashes.keys():
        return g_md5_hashes[msg]

    hasher = hashlib.md5()
    msg_text = generate_msg_text(msg).splitlines()
    for idx in range(len(msg_text)):
        line = msg_text[idx]
        msg_type = line.split(' ')[0]
        hash = None
        if get_bare_type(remove_module(msg_type)) not in primitive_types.values():
            # It is a message type and we need the md5
            if msg_type in g_ros_repr.keys():
                try:
                    hash = g_md5_hashes[msg_type]
                except KeyError:
                    hash = compute_md5(msg_type)
            else:
                hash = compute_md5_from_ast(msg_type)
            line = line.replace(msg_type, hash)
            msg_text[idx] = line
    final_text = '\n'.join(msg_text)
    hasher.update(final_text.encode())
    g_md5_hashes[msg] = hasher.hexdigest()
    return hasher.hexdigest()


def find_message_module(msg: str) -> str:
    num = 0
    ret = None
    for k, v in asnParser.g_modules.items():
        if msg in v:
            ret = k
            num += 1
    if num > 1:
        panic("Can't handle that for now...")
    return ret


def process_message(msg: str) -> dict:
    # types = asnParser.g_typesOfFile[asnFile]
    # ast = asnParser.g_astOfFile[asnFile]
    # index = None
    # definition = None
    #
    # index = types.index(msg)
    # definition = ast[index]
    try:
        definition = asnParser.g_names[msg]
    except KeyError:
        panic("I don't have the info to build message %s" % (msg))

    # print("-----------------------------------")
    # print(definition)
    # print("===================================")
    # print(def2)
    # print("-----------------------------------")

    # Only SEQUENCE or SET are considered messages
    if isinstance(definition, AsnSequence) or isinstance(definition, AsnSet):
        msg_dict = {}
        msg_dict['constants'] = []
        msg_dict['variables'] = []
        leaf_types = asnParser.g_leafTypeDict

        # First place the constants on top
        for member in definition._members:
            if leaf_types[member[1]._leafType] is 'ENUMERATED':
                enum_members = asnParser.g_names[member[1]._leafType]._members
                data_type = get_enum_data_type(enum_members)
                for em in enum_members:
                    msg_dict['constants'].append([data_type, em[0], em[1]])

        for member in definition._members:
            member_type = member[1]._leafType
            leaf_type = leaf_types[member_type]
            # TODO: We should also add a variable for the enumerated
            if leaf_type is 'CHOICE':
                panic("ROS doesn't support choice messages")
            elif leaf_type is 'ENUMERATED':
                enum_members = asnParser.g_names[member[1]._leafType]._members
                data_type = get_enum_data_type(enum_members)
                msg_dict['variables'].append([data_type, member[0]])
            elif member_type in primitive_types.keys():
                msg_dict['variables'].append(
                [primitive_types[member_type], member[0]])
            elif leaf_type is 'SEQUENCE' or leaf_type is 'SET':
                msg_dict['variables'].append(
                    [find_message_module(member_type) + '/' + member_type,
                     member[0]])
            elif leaf_type is 'SEQUENCEOF' or leaf_type is 'SETOF':
                contained_type = asnParser.g_names[member_type]._containedType
                contained_leaf_type = leaf_types[contained_type]
                min_range, max_range = asnParser.g_names[member_type]._range
                # Decide if it is a fixed or a variable size array
                # This is done by checking the array limits
                array_str = "[]"
                if min_range == max_range:
                    array_str = "[%d]" % (min_range)
                if (contained_leaf_type is 'SEQUENCE' or
                        contained_leaf_type is 'SET'):
                        msg_dict['variables'].append(
                            [find_message_module(contained_type) +
                             '/' + contained_type+array_str, member[0]])
                elif (contained_leaf_type is 'ENUMERATED'):
                    enum_members = asnParser.g_names[contained_type]._members
                    data_type = get_enum_data_type(enum_members)
                    msg_dict['variables'].append(
                        [data_type+array_str, member[0]])
                else:
                    if contained_type in primitive_types.keys():
                        msg_dict['variables'].append(
                            [primitive_types[contained_type]+array_str,
                                member[0]])
                    else:
                        msg_dict['variables'].append(
                            [find_type(contained_type)+array_str, member[0]])
            else:
                print("Finding type for %s"%member[0])
                msg_dict['variables'].append([find_type(member[1]), member[0]])
        return msg_dict


def find_type(member: AsnNode) -> str:
    # TODO: Check if the if condition is correct.
    leaf_types = [member._leafType, asnParser.g_leafTypeDict[member._leafType]]
    if any(type in supported_asn1_types for type in leaf_types):
        if any(type in 'BOOLEAN' for type in leaf_types):
            return 'bool'
        elif any(type in 'INTEGER' for type in leaf_types):
            return find_integer_type(member)
        elif any(type in 'OCTET STRING' for type in leaf_types):
            return 'uint8[]'
        elif any(type in 'REAL' for type in leaf_types):
            return find_real_type(member)
        elif any(type in 'ENUMERATED' for type in leaf_types):
            panic("ENUMERATED types shouldn't be handled here!")
        else:
            return 'string'
    else:
        panic(member._leafType + " is currently unsupported!")


def find_integer_type(member: AsnInt) -> str:
    min_val, max_val = member._range
    return get_min_integer_data_type(min_val, max_val)


def find_real_type(member: AsnReal) -> str:
    min_val, max_val = member._range
    if min_val > -3.40282e+38 and max_val < 3.40282e+38:
        return 'float32'
    else:
        return 'float64'


def find_enum_min_max_value(members: list) -> list:
    """Given a list of ENUMERATED members find the minimum and maximum used value.

    Args:
        members (list): List of the members of the enum.

    Returns:
        list: List containing the minimum and maximum value.
    """
    min_val = sys.maxsize
    max_val = -sys.maxsize - 1
    for member in members:
        val = int(member[1])
        if val > max_val:
            max_val = val
        if val < min_val:
            min_val = val
    return [min_val, max_val]


def get_min_integer_data_type(min_val: int, max_val: int) -> str:
    data_type = ''
    if min_val >= 0:
        data_type += 'u'
    data_type += 'int'

    val = int(max(abs(min_val), max_val))
    bit_num = (val.bit_length()//8) * 8
    bit_num += (val.bit_length() % 8 > 0) * 8
    data_type += str(bit_num)
    return data_type


def get_enum_data_type(members: list) -> str:
    """Gets the minimum data type required to represent the ENUMERATED values.

    Args:
        members (list): List of the members of the enum.

    Returns:
        str: String representation of the data type.

    """
    min_val, max_val = find_enum_min_max_value(members)
    return get_min_integer_data_type(min_val, max_val)


def get_bare_type(msg_type: str) -> str:
    if msg_type is None:
        return None
    if '[' in msg_type:
        return msg_type[:msg_type.find('[')]
    return msg_type


def remove_module(msg_type: str) -> str:
    if msg_type is None:
        return None
    if '/' in msg_type:
        return msg_type[msg_type.find('/')+1:]
    return msg_type


def find_type_length(var_name: str) -> int:
    count = 0
    str_len = 0
    for k, v in asnParser.g_names.items():
        if isinstance(v, AsnSequence):
            for m in v._members:
                if var_name == m[0]:
                    # print(asnParser.g_names[m[1]._leafType])
                    str_len = asnParser.g_names[m[1]._leafType]._range[1]
                    count += 1
    if count > 1:
        panic("More than 1 strings with the same name. This is not supported")
    elif count is 0:
        panic("Could not fing the string length")

    return str_len


def type_to_var(ty):
    lookup = {
        1: 'uint8_t',
        2: 'uint16_t',
        4: 'uint32_t',
        8: 'uint64_t',
    }
    return lookup[ty]

# Data Types


class EnumerationType:
    """ For data values. """

    def __init__(self, name, ty, value):
        self.name = name
        self.type = ty
        self.value = value

    def make_declaration(self, f):
        f.write('    enum { %s = %s };\n' % (self.name, self.value))


class PrimitiveDataType:
    """ Our datatype is a C/C++ primitive. """

    def __init__(self, name, ty, bytes):
        self.name = name
        self.type = ty
        self.bytes = bytes

    def make_initializer(self, f, trailer):
        f.write('      %s(0)%s\n' % (self.name, trailer))

    def make_declaration(self, f):
        f.write('    typedef %s _%s_type;\n    _%s_type %s;\n' %
                (self.type, self.name, self.name, self.name))

    def serialize(self, f):
        cn = self.name.replace("[", "").replace("]", "").split(".")[-1]
        if self.type != type_to_var(self.bytes):
            f.write('      union {\n')
            f.write('        %s real;\n' % self.type)
            f.write('        %s base;\n' % type_to_var(self.bytes))
            f.write('      } u_%s;\n' % cn)
            f.write('      u_%s.real = this->%s;\n' % (cn, self.name))
            for i in range(self.bytes):
                f.write('      *(outbuffer + offset + %d) = '
                        '(u_%s.base >> (8 * %d)) & 0xFF;\n' % (i, cn, i))
        else:
            for i in range(self.bytes):
                f.write('      *(outbuffer + offset + %d) = '
                        '(this->%s >> (8 * %d)) & 0xFF;\n' % (i, self.name, i))
        f.write('      offset += sizeof(this->%s);\n' % self.name)

    def deserialize(self, f):
        cn = self.name.replace("[", "").replace("]", "").split(".")[-1]
        if self.type != type_to_var(self.bytes):
            f.write('      union {\n')
            f.write('        %s real;\n' % self.type)
            f.write('        %s base;\n' % type_to_var(self.bytes))
            f.write('      } u_%s;\n' % cn)
            f.write('      u_%s.base = 0;\n' % cn)
            for i in range(self.bytes):
                f.write('      u_%s.base |= ((%s) (*(inbuffer + offset + %d))) << '
                        '(8 * %d);\n' % (cn, type_to_var(self.bytes), i, i))
            f.write('      this->%s = u_%s.real;\n' % (self.name, cn))
        else:
            f.write('      this->%s = '
                    '((%s) (*(inbuffer + offset)));\n' % (self.name, self.type))
            for i in range(self.bytes-1):
                f.write('      this->%s |= ((%s) (*(inbuffer + offset + %d))) << '
                        '(8 * %d);\n' % (self.name, self.type, i+1, i+1))
        f.write('      offset += sizeof(this->%s);\n' % self.name)

    def convert_from(self, f, spacing):
        f.write(spacing + '%s = var->%s;\n' % (self.name, self.name))

    def convert_to(self, f, spacing):
        f.write(spacing + 'var->%s = %s;\n' % (self.name, self.name))


class MessageDataType(PrimitiveDataType):
    """ For when our data type is another message. """

    def make_initializer(self, f, trailer):
        f.write('      %s()%s\n' % (self.name, trailer))

    def serialize(self, f):
        f.write('      offset += this->%s.serialize(outbuffer + offset);\n' %
                self.name)

    def deserialize(self, f):
        f.write('      offset += this->%s.deserialize(inbuffer + offset);\n' %
                self.name)

    def convert_from(self, f, spacing):
        f.write(spacing + '%s.fromASN1(&var->%s);\n' % (self.name, self.name))

    def convert_to(self, f, spacing):
        f.write(spacing + '%s.toASN1(&var->%s);\n' % (self.name, self.name))

class StringDataType(PrimitiveDataType):
    """ Need to convert to signed char *. """

    def make_initializer(self, f, trailer):
        f.write('      %s("")%s\n' % (self.name, trailer))

    def make_declaration(self, f):
        # In declaration we need to find the lengh from the type
        # print ("string length:", find_type_length(self.name))

        # f.write('    typedef const char* _%s_type;\n    _%s_type %s;\n' %
        # Length should be increased by 1 for NULL termination
        length = find_type_length(self.name)
        f.write('    typedef char _%s_type[%d];\n    _%s_type %s;\n' %
                (self.name, length + 1, self.name, self.name))

    def serialize(self, f):
        cn = self.name.replace("[", "").replace("]", "")
        f.write('      uint32_t length_%s = strlen(this->%s);\n' % (cn, self.name))
        f.write('      varToArr(outbuffer + offset, length_%s);\n' % cn)
        f.write('      offset += 4;\n')
        f.write('      memcpy(outbuffer + offset, this->%s, length_%s);\n' %
                (self.name, cn))
        f.write('      offset += length_%s;\n' % cn)

    def deserialize(self, f):
        cn = self.name.replace("[", "").replace("]", "")
        f.write('      uint32_t length_%s;\n' % cn)
        f.write('      arrToVar(length_%s, (inbuffer + offset));\n' % cn)
        f.write('      offset += 4;\n')
        f.write('      for(unsigned int k= offset; k< offset+length_%s; ++k){\n' %
                cn)  # shift for null character
        f.write('        inbuffer[k-1]=inbuffer[k];\n')
        f.write('      }\n')
        f.write('      inbuffer[offset+length_%s-1]=0;\n' % cn)
        f.write('      this->%s = (char *)(inbuffer + offset-1);\n' % self.name)
        f.write('      offset += length_%s;\n' % cn)

    def convert_from(self, f, spacing):
        f.write(spacing + 'strncpy(%s, var->%s, sizeof(%s));\n' %
                (self.name, self.name, self.name))

    def convert_to(self, f, spacing):
        f.write(spacing + 'strncpy(var->%s, %s, sizeof(var->%s));\n' %
                (self.name, self.name, self.name))


class TimeDataType(PrimitiveDataType):

    def __init__(self, name, ty, bytes):
        self.name = name
        self.type = ty
        self.sec = PrimitiveDataType(name+'.sec', 'uint32_t', 4)
        self.nsec = PrimitiveDataType(name+'.nsec', 'uint32_t', 4)

    def make_initializer(self, f, trailer):
        f.write('      %s()%s\n' % (self.name, trailer))

    def make_declaration(self, f):
        f.write('    typedef %s _%s_type;\n    _%s_type %s;\n' %
                (self.type, self.name, self.name, self.name))

    def serialize(self, f):
        self.sec.serialize(f)
        self.nsec.serialize(f)

    def deserialize(self, f):
        self.sec.deserialize(f)
        self.nsec.deserialize(f)

    def convert_from(self, f, spacing):
        f.write(spacing + '%s.sec = var->%s.sec;\n' % (self.name, self.name))
        f.write(spacing + '%s.nsec = var->%s.nsec;\n' % (self.name, self.name))

    def convert_to(self, f, spacing):
        f.write(spacing + 'var->%s.sec = %s.sec;\n' % (self.name, self.name))
        f.write(spacing + 'var->%s.nsec = %s.nsec;\n' % (self.name, self.name))


class ArrayDataType(PrimitiveDataType):

    def __init__(self, name, ty, bytes, cls, array_size=None):
        self.name = name
        self.type = ty
        self.bytes = bytes
        self.size = array_size
        self.cls = cls

    def make_initializer(self, f, trailer):
        if self.size is None:
            f.write('      %s_length(0), %s(NULL)%s\n' %
                    (self.name, self.name, trailer))
        else:
            f.write('\t%s()%s\n' % (self.name, trailer))

    def make_declaration(self, f):
        if self.size is None:
            length = find_type_length(self.name)
            f.write('    uint32_t %s_length;\n' % self.name)
            # f.write('    typedef %s _%s_type;\n' % (self.type, self.name))
            f.write('    %s st_%s;\n' % (self.type, self.name))  # static instance for copy
            f.write('    %s %s[%d];\n' % (self.type, self.name, length))
        else:
            f.write('    %s %s[%d];\n' % (self.type, self.name, self.size))

    def serialize(self, f):
        c = self.cls(self.name+"[i]", self.type, self.bytes)
        if self.size is None:
            # serialize length
            f.write('      *(outbuffer + offset + 0) = '
                    '(this->%s_length >> (8 * 0)) & 0xFF;\n' % self.name)
            f.write('      *(outbuffer + offset + 1) = '
                    '(this->%s_length >> (8 * 1)) & 0xFF;\n' % self.name)
            f.write('      *(outbuffer + offset + 2) = '
                    '(this->%s_length >> (8 * 2)) & 0xFF;\n' % self.name)
            f.write('      *(outbuffer + offset + 3) = '
                    '(this->%s_length >> (8 * 3)) & 0xFF;\n' % self.name)
            f.write('      offset += sizeof(this->%s_length);\n' % self.name)
            f.write('      for( uint32_t i = 0; i < %s_length; i++){\n' % self.name)
            c.serialize(f)
            f.write('      }\n')
        else:
            f.write('      for( uint32_t i = 0; i < %d; i++){\n' % (self.size))
            c.serialize(f)
            f.write('      }\n')

    def deserialize(self, f):
        if self.size is None:
            c = self.cls("st_"+self.name, self.type, self.bytes)
            # deserialize length
            f.write('      uint32_t %s_lengthT = '
                    '((uint32_t) (*(inbuffer + offset)));\n' % self.name)
            f.write('      %s_lengthT |= ((uint32_t) '
                    '(*(inbuffer + offset + 1))) << (8 * 1);\n' % self.name)
            f.write('      %s_lengthT |= ((uint32_t) '
                    '(*(inbuffer + offset + 2))) << (8 * 2);\n' % self.name)
            f.write('      %s_lengthT |= ((uint32_t) '
                    '(*(inbuffer + offset + 3))) << (8 * 3);\n' % self.name)
            f.write('      offset += sizeof(this->%s_length);\n' % self.name)
            f.write('      if(%s_lengthT > %s_length)\n' % (self.name, self.name))
            f.write('        this->%s = '
                    '(%s*)realloc(this->%s, %s_lengthT * sizeof(%s));\n' %
                    (self.name, self.type, self.name, self.name, self.type))
            f.write('      %s_length = %s_lengthT;\n' % (self.name, self.name))
            # copy to array
            f.write('      for( uint32_t i = 0; i < %s_length; i++){\n' %
                    (self.name))
            c.deserialize(f)
            f.write('        memcpy( &(this->%s[i]), &(this->st_%s), sizeof(%s));\n'
                    % (self.name, self.name, self.type))
            f.write('      }\n')
        else:
            c = self.cls(self.name+"[i]", self.type, self.bytes)
            f.write('      for( uint32_t i = 0; i < %d; i++){\n' % (self.size))
            c.deserialize(f)
            f.write('      }\n')

    def convert_from(self, f, spacing):
        f.write(spacing + '{\n')
        if self.size is None:
            # Use length
            f.write(spacing + '  uint32_t length = var->%s.nCount;\n' % self.name)
            f.write(spacing + '  %s_length = length;\n' % self.name)
        else:
            # Copy all
            f.write(spacing + '  uint32_t length = %d;\n' % self.size)
        f.write(spacing + '  memcpy(%s, var->%s, length * sizeof(*%s));\n' %
                (self.name, self.name, self.name))
        f.write(spacing + '}\n')


    def convert_to(self, f, spacing):
        f.write(spacing + '{\n')
        if self.size is None:
            # Use length
            f.write(spacing + '  uint32_t length = %s_length;\n' % self.name)
            f.write(spacing + '  var->%s.nCount = length;\n' % self.name)
        else:
            # Copy all
            f.write(spacing + '  uint32_t length = %d;\n' % self.size)
        f.write(spacing + '  memcpy(var->%s, %s, length * sizeof(*%s));\n' %
                (self.name, self.name, self.name))
        f.write(spacing + '}\n')



# Messages

class Message:
    """ Parses message definitions into something we can export. """
    global ROS_TO_EMBEDDED_TYPES

    def __init__(self, name: str, package: str, definition: str, md5: str) -> None:

        self.name = name            # name of message/class
        self.package = package      # package we reside in
        self.md5 = md5              # checksum
        self.includes = list()      # other files we must include

        self.data = list()          # data types for code generation
        self.enums = list()

        self.message_text = definition

        # parse definition
        definition = definition.splitlines()
        for line in definition:
            # prep work
            line = line.strip().rstrip()
            value = None
            # Remove the comments
            if line.find("#") > -1:
                line = line[0:line.find("#")]

            # Get the value of a variable if present
            if line.find("=") > -1:
                try:
                    value = line[line.find("=")+1:]
                except Exception as e:
                    value = '"' + line[line.find("=")+1:] + '"'
                line = line[0:line.find("=")]

            # find package/class name
            line = line.replace("\t", " ")
            l = line.split(" ")
            while "" in l:
                l.remove("")
            if len(l) < 2:
                continue
            ty, name = l[0:2]
            if value is not None:
                self.enums.append(EnumerationType(name, ty, value))
                continue

            try:
                type_package, type_name = ty.split("/")
            except Exception as e:
                type_package = None
                type_name = ty
            type_array = False
            if type_name.find('[') > 0:
                type_array = True
                try:
                    type_array_size = int(type_name[
                        type_name.find('[')+1:type_name.find(']')])
                except Exception as e:
                    type_array_size = None
                type_name = type_name[0:type_name.find('[')]

            # convert to C type if primitive, expand name otherwise
            try:
                code_type = ROS_TO_EMBEDDED_TYPES[type_name][0]
                size = ROS_TO_EMBEDDED_TYPES[type_name][1]
                cls = ROS_TO_EMBEDDED_TYPES[type_name][2]
                for include in ROS_TO_EMBEDDED_TYPES[type_name][3]:
                    if include not in self.includes:
                        self.includes.append(include)
            except Exception as e:
                print("Type %s not in ROS_TO_EMBEDDED_TYPES" % type_name)
                if type_package is None and self.package is not None:
                    type_package = self.package
                if type_package is not None:
                    if type_package+"/"+type_name not in self.includes:
                        self.includes.append(type_package+"/"+type_name)
                else:
                    if type_name not in self.includes:
                        self.includes.append(type_name)
                cls = MessageDataType
                if type_package is not None:
                    code_type = type_package + "::" + type_name
                else:
                    code_type = type_name
                size = 0
            if type_array:
                self.data.append(
                    ArrayDataType(name, code_type, size, cls, type_array_size))
            else:
                self.data.append(cls(name, code_type, size))

    def _write_serializer(self, f):
                # serializer
        f.write('    virtual int serialize(unsigned char *outbuffer) const\n')
        f.write('    {\n')
        f.write('      int offset = 0;\n')
        for d in self.data:
            d.serialize(f)
        f.write('      return offset;\n')
        f.write('    }\n')
        f.write('\n')

    def _write_deserializer(self, f):
        # deserializer
        f.write('    virtual int deserialize(unsigned char *inbuffer)\n')
        f.write('    {\n')
        f.write('      int offset = 0;\n')
        for d in self.data:
            d.deserialize(f)
        f.write('      return offset;\n')
        f.write('    }\n')
        f.write('\n')

    def _write_std_includes(self, f):
        f.write('#include <stdint.h>\n')
        f.write('#include <string.h>\n')
        f.write('#include <stdlib.h>\n')
        f.write('#include "ros/msg.h"\n')
        # TODO (Niko): Check if this is correct. Actually asn1scc generates per
        # file headers while we generate per message.
        # f.write('#include "%s.h"\n' % self.name.lower())

    def _write_msg_includes(self, f):
        for i in self.includes:
            if find_message_module(remove_module(i)) is self.package:
                f.write('#include "%s.h"\n' % remove_module(i))
            elif remove_module(i) in ROS_TO_EMBEDDED_TYPES.keys():
                f.write('#include "%s.h"\n' % ROS_TO_EMBEDDED_TYPES[remove_module(i)][3][0])
            else:
                f.write('#include "../%s.h"\n' % i)

    def _write_constructor(self, f):
        f.write('    %s()%s\n' % (self.name, ':' if self.data else ''))
        if self.data:
            for d in self.data[:-1]:
                d.make_initializer(f, ',')
            self.data[-1].make_initializer(f, '')
        f.write('    {\n    }\n\n')

    def _write_data(self, f):
        for d in self.data:
            d.make_declaration(f)
        for e in self.enums:
            e.make_declaration(f)
        f.write('\n')

    def _write_getType(self, f):
        if self.package is not None:
            f.write('    const char * getType(){ return "%s/%s"; };\n' %
                    (self.package, self.name))
        else:
            f.write('    const char * getType(){ return "%s"; };\n' %
                    (self.name))

    def _write_getMD5(self, f):
        f.write('    const char * getMD5(){ return "%s"; };\n' % self.md5)

    def _write_conversion(self, f):
        f.write('\n')
        f.write('    void fromASN1(asn1scc%s *var)\n' % self.name)
        f.write('    {\n')
        if self.data:
            for d in self.data:
                # print(d)
                if isinstance(d, MessageDataType):
                    d.convert_from(f, '      ')
                elif isinstance(d, StringDataType):
                    d.convert_from(f, '      ')
                elif isinstance(d, TimeDataType):
                    d.convert_from(f, '      ')
                elif isinstance(d, ArrayDataType):
                    d.convert_from(f, '      ')
                elif isinstance(d, PrimitiveDataType):
                    d.convert_from(f, '      ')
                else:
                    panic("I don't know how to handle %s data type!" % self.name)
        f.write('    }\n\n')
        f.write('\n')
        f.write('    void toASN1(asn1scc%s *var)\n' % self.name)
        f.write('    {\n')
        if self.data:
            for d in self.data:
                if isinstance(d, MessageDataType):
                    d.convert_to(f, '      ')
                elif isinstance(d, StringDataType):
                    d.convert_to(f, '      ')
                elif isinstance(d, TimeDataType):
                    d.convert_to(f, '      ')
                elif isinstance(d, ArrayDataType):
                    d.convert_to(f, '      ')
                elif isinstance(d, PrimitiveDataType):
                    d.convert_to(f, '      ')
                else:
                    panic("I don't know how to handle %s data type!" % self.name)
        f.write('    }\n\n')

    def _write_impl(self, f):
        f.write('class %s : public ros::Msg\n' % self.name)
        f.write('{\n')
        f.write('  public:\n')
        self._write_data(f)
        self._write_constructor(f)
        self._write_serializer(f)
        self._write_deserializer(f)
        self._write_getType(f)
        self._write_getMD5(f)
        self._write_conversion(f)
        f.write('\n')
        f.write('};\n')

    def make_header(self, f):
        if self.package is not None:
            f.write('#ifndef _ROS_%s_%s_h\n' % (self.package, self.name))
            f.write('#define _ROS_%s_%s_h\n' % (self.package, self.name))
        else:
            f.write('#ifndef _ROS_%s_h\n' % (self.name))
            f.write('#define _ROS_%s_h\n' % (self.name))
        f.write('\n')
        self._write_std_includes(f)
        self._write_msg_includes(f)

        f.write('\n')
        if self.package is not None:
            f.write('namespace %s\n' % self.package)
            f.write('{\n')
        f.write('\n')
        self._write_impl(f)
        f.write('\n')
        if self.package is not None:
            f.write('}\n')
        f.write('#endif')

    def make_msg(self, f):
        f.write(self.message_text)


ROS_TO_EMBEDDED_TYPES = {
    'bool':     ('bool',              1, PrimitiveDataType, []),
    'byte':     ('int8_t',            1, PrimitiveDataType, []),
    'int8':     ('int8_t',            1, PrimitiveDataType, []),
    'char':     ('uint8_t',           1, PrimitiveDataType, []),
    'uint8':    ('uint8_t',           1, PrimitiveDataType, []),
    'int16':    ('int16_t',           2, PrimitiveDataType, []),
    'uint16':   ('uint16_t',          2, PrimitiveDataType, []),
    'int32':    ('int32_t',           4, PrimitiveDataType, []),
    'uint32':   ('uint32_t',          4, PrimitiveDataType, []),
    'int64':    ('int64_t',           8, PrimitiveDataType, []),
    'uint64':   ('uint64_t',          8, PrimitiveDataType, []),
    'float32':  ('float',             4, PrimitiveDataType, []),
    'float64':  ('double',            8, PrimitiveDataType, []),
    'time':     ('ros::Time',         8, TimeDataType, ['ros/time']),
    'duration': ('ros::Duration',     8, TimeDataType, ['ros/duration']),
    'string':   ('char*',             0, StringDataType, []),
    'Header':   ('std_msgs::Header',  0, MessageDataType, ['std_msgs/Header'])
}
