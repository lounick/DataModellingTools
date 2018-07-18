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
    'T-Time': 'time', 'T-Time': 'duration', 'T-Int8': 'byte', 'T-UInt8': 'char'}

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

def Version() -> None:
    print("Code generator: " +
          "$Id: python_A_mapper.py $")  # pragma: no cover


def OnStartup(unused_modelingLanguage: str, asnFile: str, outputDir: str, badTypes: SetOfBadTypenames) -> None:
    # print(asnParser.g_modules)
    # print(asnParser.g_names)
    # print(asnParser.g_leafTypeDict)
    # print(asnParser.g_typesOfFile[asnFile])
    # print(asnParser.g_astOfFile[asnFile])
    if not asnFile.endswith(".asn"):
        panic("The ASN.1 grammar file (%s) doesn't end in .asn" %
              asnFile)  # pragma: no cover

    global g_ros_repr
    g_ros_repr = {}

    for msg in asnParser.g_typesOfFile[asnFile]:
        if (isinstance(asnParser.g_names[msg], AsnSequence) or
                isinstance(asnParser.g_names[msg], AsnSet)):
                g_ros_repr[msg] = process_message(msg)
        # compute_md5(asnFile, msg)
    # For each SEQUENCE we need to generate a message header
    # Format a ROS message based on the ASN.1 message
    # Calculate the MD5
    # print(g_ros_repr)
    print("")

    for msg in asnParser.g_typesOfFile[asnFile]:
        if (isinstance(asnParser.g_names[msg], AsnSequence) or
                isinstance(asnParser.g_names[msg], AsnSet)):
                print(compute_md5(msg))
                print("")


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


def compute_md5_from_ast(msg: str) -> str:
    global g_ros_repr
    msg_dict = process_message(msg)
    g_ros_repr[msg] = msg_dict
    return compute_md5(msg)


def compute_md5(msg: str) -> str:
    print("Calculating md5 for message: %s" % (msg))

    global g_ros_repr
    global g_md5_hashes

    if msg in g_md5_hashes.keys():
        return g_md5_hashes[msg]

    definition = g_ros_repr[msg]

    buff = StringIO()

    for const in definition['constants']:
        buff.write("%s %s=%s\n" % (const[0], const[1], const[2]))

    for var in definition['variables']:
        if get_bare_type(var[0]) in primitive_types.values():
            buff.write("%s %s\n" % (var[0], var[1]))
        else:
            # TODO: Must compute the md5 of the other message type
            if var[0] in g_ros_repr.keys():
                try:
                    hash = g_md5_hashes[var[0]]
                except KeyError:
                    hash = compute_md5(var[0])
                buff.write("%s %s\n" % (hash, var[1]))
            else:
                buff.write("%s %s\n" % (compute_md5_from_ast(var[0]), var[1]))

    hasher = hashlib.md5()
    # print(buff.getvalue().strip())
    hasher.update(buff.getvalue().strip().encode())
    g_md5_hashes[msg] = hasher.hexdigest()
    return hasher.hexdigest()


def process_message(msg: str) -> dict:
    # types = asnParser.g_typesOfFile[asnFile]
    # ast = asnParser.g_astOfFile[asnFile]
    # index = None
    # definition = None
    #
    # index = types.index(msg)
    # definition = ast[index]
    definition = asnParser.g_names[msg]

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
            if leaf_type is 'ENUMERATED':
                enum_members = asnParser.g_names[member[1]._leafType]._members
                data_type = get_enum_data_type(enum_members)
                msg_dict['variables'].append([data_type, member[0]])
            elif leaf_type is 'SEQUENCE' or leaf_type is 'SET':
                msg_dict['variables'].append([member_type, member[0]])
            elif leaf_type is 'SEQUENCEOF' or leaf_type is 'SETOF':
                contained_type = asnParser.g_names[member_type]._containedType
                contained_leaf_type = leaf_types[contained_type]
                min_range, max_range = asnParser.g_names[member_type]._range
                array_str = "[]"
                if min_range == max_range:
                    array_str = "[%d]" % (min_range)
                if (contained_leaf_type is 'SEQUENCE' or
                        contained_leaf_type is 'SET'):
                        msg_dict['variables'].append([contained_type+array_str, member[0]])
                elif (contained_leaf_type is 'ENUMERATED'):
                    enum_members = asnParser.g_names[contained_type]._members
                    data_type = get_enum_data_type(enum_members)
                    msg_dict['variables'].append([data_type+array_str, member[0]])
                else:
                    # Decide if it is a fixed or a variable size array
                    # This is done by checking the array limits
                    if contained_type in primitive_types.keys():
                        msg_dict['variables'].append([primitive_types[contained_type]+array_str, member[0]])
                    else:
                        msg_dict['variables'].append([find_type(contained_type)+array_str, member[0]])
            elif member_type in primitive_types.keys():
                msg_dict['variables'].append([primitive_types[member_type], member[0]])
            else:
                msg_dict['variables'].append([find_type(member[1]), member[0]])
        return msg_dict


def find_type(member: AsnNode) -> str:
    if member._leafType in supported_asn1_types:
        if member._leafType is 'BOOLEAN':
            return 'bool'
        elif member._leafType is 'INTEGER':
            return find_integer_type(member)
        elif member._leafType is 'OCTET STRING':
            return 'uint8[]'
        elif member._leafType is 'REAL':
            return find_real_type(member)
        elif member._leafType is 'ENUMERATED':
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
