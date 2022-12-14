#!BPY

bl_info = {
    "name": "Super Smash Bros. Ultimate Animation Exporter",
    "description": "Exports animation data to NUANMB files (binary animation format used by some games developed by Bandai-Namco)",
    "author": "Carlos, Richard Qian (Worldblender), Ploaj",
    "version": (1, 0, 0),
    "blender": (2, 80, 0),
    "location": "File > Export",
    "category": "Import-Export"}

import bpy, enum, io, math, mathutils, os, struct, time, numpy

class AnimType(enum.Enum):
    Transform = 1
    Visibility = 2
    Material = 4
    Camera = 5

class AnimTrackFlags(enum.Enum):
    Transform = 1
    Texture = 2
    Float = 3
    PatternIndex = 5
    Boolean = 8
    Vector = 9
    Direct = 256
    ConstTransform = 512
    Compressed = 1024
    Constant = 1280

def write_c_string(f, s):
    write_chars(f, s)
    write_byte(f, 0) # Null terminator

# Writes a variable number of empty bytes depending on necessary alignment
def pad(f, alignment):
    while(f.tell() % alignment):
        write_byte(f, 0)

def write_byte(f, val):
    f.write(struct.pack('<B', val))

def write_short(f, val):
    f.write(struct.pack('<h', val))

def write_ushort(f, val):
    f.write(struct.pack('<H', val))

def write_int(f, val):
    f.write(struct.pack('<i', val))

def write_uint(f, val):
    f.write(struct.pack('<I', val))

def write_float(f, val):
    f.write(struct.pack('<f', val))

def write_long64(f, val):
    f.write(struct.pack('<q', val))

def write_ulong64(f, val):
    f.write(struct.pack('<Q', val))

def write_chars(f, chars):
    f.write(struct.pack('<{}s'.format(len(chars)), chars.encode()))

def write_byte_array(f, ba):
    f.write(ba.getbuffer())

def write_bytes(f, bytes):
    for byte in bytes:
        write_byte(f, byte)

# Some longs contain an offset to data, but that offset isn't the absolute file offset its
# relative to that long's position in the file/buffer.
def write_rel_offset(f, offsetPos):
    # Backup file write pos
    filePosBackup = f.tell()

    f.seek(offsetPos) # Relative to file start
    write_long64(f, filePosBackup - offsetPos) # Value written is the offset from the offsetPos to the data.

    f.seek(filePosBackup)

class Group:
    def __init__(self):
        self.nodesAnimType = 0
        self.nodesOffsetPos = 0
        self.nodesOffset = 0
        self.nodes = []

class Node:
    def __init__(self):
        self.name = ""
        self.nodeNameOffset = 0
        self.nodeNameOffsetPos = 0
        self.nodeDataOffset = 0
        self.nodeDataOffsetPos = 0
        self.nodeAnimTrack = NodeAnimTrack()
        self.materialSubNodes = [] #hack for materials + camera.

class NodeAnimTrack:
    def __init__(self):
        self.name = ""
        self.type = ""
        self.typeOffset = 0
        self.typeOffsetPos = 0
        self.flags = 0
        self.frameCount = 0
        self.dataOffset = 0
        self.dataSize = 0
        self.unk3 = 0
        self.animationTrack = [] # could be an array of matrix4x4, or vector4, or bools, or floats, or...

    def __repr__(self):
        return "Node name: " + str(self.name) + "\t| Type: " + str(self.type) + "\t| Flags: " + str(self.flags) + "\t| # of frames: " + str(self.frameCount) + "\t| Data offset: " + str(self.dataOffset) + "\t| Data size: " + str(self.dataSize) + "\n"

class Quantanizer:
    def __init__(self, valueArray, epsilon):
        de_nan_array(valueArray)
        #self.values = valueArray
        self.min = min(valueArray)
        self.max = max(valueArray)
        if math.isclose(self.min, 1, rel_tol=1e-04):
            self.min = 1
        if math.isclose(self.max, 1, rel_tol=1e-04):
            self.max = 1
        if math.isclose(self.min, 0, abs_tol=1e-04):
            self.min = 0
        if math.isclose(self.max, 0, abs_tol=1e-04):
            self.max = 0
        if math.isclose(self.min, self.max, rel_tol=1e-04):
            self.min = self.max
        self.constant = self.min == self.max
        self.bitCount = self.calc_bit_count(epsilon, valueArray)

    def __repr__(self):
        return "min: " + str(self.min) + " max: " + str(self.max) + " constant: " + str(self.constant)  + " bitCount: " + str(self.bitCount) + "\t"

    def calc_bit_count(self, epsilon, valueArray):
        if self.constant:
            return 0
        while epsilon < 1:
            for bits in range(1, 31):
                if self.compute_error(bits, valueArray) < epsilon:
                    return bits
            epsilon *= 2
        return -1 # Failed to find an optimal bit count. idk if this ever happens

    def compute_error(self, bits, valueArray):
        e = 0
        if self.constant:
            return 0
        for v in valueArray:
            ce = abs(v - self.decompressed_value(v,bits))
            e = max(e, ce)
        return e

    def decompressed_value(self, v, bits):
        qv = quantanization_value(bits)
        if qv == 0:
            return 0

        return lerp(self.min, self.max, 0, 1, self.quantanize(v, bits) / quantanization_value(bits))

    def quantanize(self, v, bits):
        if v <= self.min:
            return 0

        if v >= self.max:
            return quantanization_value(bits)

        # Quantanized value, which is supposed to be an integer
        quantanized = (v - self.min) / (self.max - self.min) * quantanization_value(bits)
        quantanized = math.trunc(quantanized)
        return quantanized

def quantanization_value(bitCount):
    v = 0
    for i in range(0, bitCount):
        v |= 1 << i
    return v

# A standard linear interpolation function for individual values
def lerp(av, bv, v0, v1, factor):
    if (v0 == v1):
        return av
    if (factor == v0):
        return av
    if (factor == v1):
        return bv

    mu = (factor - v0) / (v1 - v0)
    return (av * (1 - mu)) + (bv * mu)

def de_nan_array(va):
    for v in va:
        if math.isnan(v):
            print("NaN")
            v = 0.0

def material_group_hacks(f, g):
    pad(f, 0x8) # 8-byte alignment for arrays
    write_rel_offset(f, g.nodesOffsetPos)
    for node in g.nodes:
        node.nodeNameOffsetPos = f.tell()
        write_long64(f, 0) # Placeholder offset, node name e.g. "EyeL"
        node.nodeDataOffsetPos = f.tell()
        write_long64(f, 0) # Placeholder offset, probably node data offset
        write_long64(f, len(node.materialSubNodes)) #Material nodes have subnodes, e.g. CustomBoolean1. Length is 9 for "EyeL"
        pad(f, 0x8)

    for node in g.nodes:
        pad(f, 0x4) # 4-byte alignent for strings, about to write "EyeL"
        write_rel_offset(f, node.nodeNameOffsetPos)
        write_c_string(f, node.name)
        pad(f, 0x8) # 8-byte alignment for arrays
        write_rel_offset(f, node.nodeDataOffsetPos)

        for msn in node.materialSubNodes:
            nat = msn.nodeAnimTrack
            nat.typeOffsetPos = f.tell()
            write_long64(f, 0) # A temp offset to the type name
            write_uint(f, nat.flags)
            write_uint(f, nat.frameCount)
            write_uint(f, nat.unk3)
            write_uint(f, nat.dataOffset)
            write_long64(f, nat.dataSize)
            pad(f, 0x8)

        for msn in node.materialSubNodes:
            nat = msn.nodeAnimTrack
            pad(f, 0x4) # 4-byte alignement for strings, about to write "CustomVector0"
            write_rel_offset(f, nat.typeOffsetPos)
            write_c_string(f, nat.type)
            # ...Repeat for all custom vectors, looks like the type names are contiguous

    # Umm after this the massive unified animation data buffer gets written
    # What happened to the custom bools and floats?
    # Turns out studiosb doesnt write them out

def write_group_array(f, groups):

    # Write out some preliminary node stuff for all groups
    for g in groups:
        write_long64(f, g.nodesAnimType) # Write the AnimType of the group, check out the enums
        g.nodesOffsetPos = f.tell()
        write_long64(f, 0) # Temp 'NodeOffset'
        write_long64(f, len(g.nodes)) # NodeCount, a 'Node' could be something like a bone in an AnimTrack
        pad(f, 0x8) # Probably not necessary since just wrote 3 long64s...

    # Now actually write out the nodes
    for g in groups:
        if (g.nodesAnimType == AnimType.Material.value or g.nodesAnimType == AnimType.Camera.value):
            material_group_hacks(f, g)
            continue

        pad(f, 0x8) # 8-byte alignment for arrays
        write_rel_offset(f, g.nodesOffsetPos)

        for node in g.nodes: # Node Prep
            node.nodeNameOffsetPos = f.tell()
            write_long64(f, 0) # Temp node name offset
            node.nodeDataOffsetPos = f.tell()
            write_long64(f, 0) # Temp node data offset
            write_long64(f, 1) # 'Array.length', but it seems like only materials have multiple sub nodes in the array
            pad(f, 0x8) # Probably not necessary, since only longs got written

        for node in g.nodes: # Node Finalizer Loop
            pad(f, 0x4) # 4-byte alignement for strings
            write_rel_offset(f, node.nodeNameOffsetPos) # About to write name so go fill-in offset
            write_c_string(f, node.name) # e.g "ArmL"
            pad(f, 0x8) # 8-byte alignment for arrays
            write_rel_offset(f, node.nodeDataOffsetPos) # Node data? like, the flags,framecount, AnimType, etc
            # Time to write out the node data, order is important
            nat = node.nodeAnimTrack
            nat.typeOffsetPos = f.tell()
            write_long64(f, 0) # A temp offset to the TypeName. Idk why its done this way rather than just write out the enum
            write_uint(f, nat.flags)
            write_uint(f, nat.frameCount)
            write_uint(f, nat.unk3)
            write_uint(f, nat.dataOffset) # Shouldn't this be unknown at this point? Already known in studiosb, which means the data buffer was already calculated at this point
            write_long64(f, nat.dataSize) # guess I'll just premake the animation data buffer.
                                          # dataOffset refers to its offset in the unified data buffer that contains all data for all nodes in all tracks.
                                          # so, data offset will be 0 for the first entry
            pad(f, 0x8)
            pad(f, 0x4) # 4-byte alignement for strings
            write_rel_offset(f, nat.typeOffsetPos)
            write_c_string(f, nat.type)

def write_nuanmb(f, animBuffer, groups, finalFrameIndex, animName):
    write_chars(f, "HBSS")
    write_int(f, 0x40) # 4 bytes
    pad(f, 0x10) # 16-Byte Aligned Header
    write_uint(f, 0x414E494D) # Magic, 4 bytes
    write_ushort(f, 0x0002) # VersionMajor, 2 bytes
    write_ushort(f, 0x0000) # VersionMinor, 2 bytes
    write_float(f, finalFrameIndex) # FFI, 4 bytes
    write_ushort(f, 0x0001) # Unk1, 2 bytes
    write_ushort(f, 0x0003) # Unk2, 2 bytes

    animNameOffset = f.tell()
    write_long64(f, 0) # Placeholder relative offset for anim name, 8 bytes

    groupOffset = f.tell()
    write_long64(f, 0) # Placeholder relative offset for animation arrays, aka the 'GroupOffset', 8 bytes

    write_long64(f, len(groups)) # e.g '3' for anim w/ 'Transform', 'Visibility', 'Material' tracks, 8 bytes

    bufferOffset = f.tell()
    write_long64(f, 0) # Placeholder relative offset for GroupData "BufferOffset"

    write_long64(f, animBuffer.getbuffer().nbytes) # "BufferSize"

    pad(f, 0x8) # 8 bytes

    pad(f, 0x4) # 4 bytes, necessary padding because file name string will be written
    write_rel_offset(f, animNameOffset) #Nows a good time to fix the temp offset
    write_c_string(f, animName) #variable bytes
    pad(f, 0x4) # 4 bytes, apparently  strings are padded before and after?

    pad(f, 0x8) # 8-byte alignement for arrays and matl data objects
    write_rel_offset(f, groupOffset)
    write_group_array(f, groups)

    # Ready to write big buffer
    pad(f, 0x8)
    write_rel_offset(f, bufferOffset)
    write_byte_array(f, animBuffer)

def make_anim_buffer(context, groups, compression):
    b = io.BytesIO()
    for g in groups:
        for node in g.nodes:
            if node.materialSubNodes: #Material or Camera
                for sn in node.materialSubNodes:
                    write_track_from_nat(b, sn.nodeAnimTrack, compression)
            else: #Normal
                write_track_from_nat(b, node.nodeAnimTrack, compression)
    return b

def write_uncompressed_tranform(b, nat):
    for af in nat.animationTrack: # af means "AnimationFrame"
        '''
        Smash matrix
          0   1   2   3
        0 SX  SY  SZ  N/A
        1 RX  RY  RZ  RW
        2 PX  PY  PZ  0
        '''

        sx = af[0][0]; sy = af[0][1]; sz = af[0][2]
        rx = af[1][0]; ry = af[1][1]; rz = af[1][2]; rw = af[1][3]
        px = af[2][0]; py = af[2][1]; pz = af[2][2]

        write_float(b, sx); write_float(b, sy); write_float(b, sz)
        write_float(b, rx); write_float(b, ry); write_float(b, rz); write_float(b, rw)
        write_float(b, px); write_float(b, py); write_float(b, pz);
        write_float(b, 0); # Always 0?

        # Wrote Direct, so set Direct Flags
        nat.flags |= AnimTrackFlags.Direct.value

def all_same(nat):
    allSame = True
    first = nat.animationTrack[0]
    for af in nat.animationTrack:
        if first != af:
            allSame = False
            break
    return allSame

def write_const_transform(b, nat):
    af = nat.animationTrack[0]

    sx = af[0][0]; sy = af[0][1]; sz = af[0][2]
    rx = af[1][0]; ry = af[1][1]; rz = af[1][2]; rw = af[1][3]
    px = af[2][0]; py = af[2][1]; pz = af[2][2]

    write_float(b, sx); write_float(b, sy); write_float(b, sz)
    write_float(b, rx); write_float(b, ry); write_float(b, rz); write_float(b, rw)
    write_float(b, px); write_float(b, py); write_float(b, pz);
    write_float(b, 0); #Always 0?

    nat.flags |= AnimTrackFlags.ConstTransform.value

def write_compressed_transform(b, nat):

    nat.flags |= AnimTrackFlags.Compressed.value

    epsilon = 0.000002 # Maybe allow this to be set by user, but might just be confusing.

    # Make the 'Animation Track' into a numpy array for vertical slicing
    at = numpy.array(nat.animationTrack)

    sx = Quantanizer(at[:, 0, 0], epsilon)
    sy = Quantanizer(at[:, 0, 1], epsilon)
    sz = Quantanizer(at[:, 0, 2], epsilon)
    rx = Quantanizer(at[:, 1, 0], epsilon)
    ry = Quantanizer(at[:, 1, 1], epsilon)
    rz = Quantanizer(at[:, 1, 2], epsilon)
    px = Quantanizer(at[:, 2, 0], epsilon)
    py = Quantanizer(at[:, 2, 1], epsilon)
    pz = Quantanizer(at[:, 2, 2], epsilon)

    hasScale = not (sx.constant and sy.constant and sz.constant)
    hasRotation = not (rx.constant and ry.constant and rz.constant)
    hasPosition = not (px.constant and py.constant and pz.constant)

    """
    print("nat.name = " + str(nat.name))
    print("sx:" + str(sx) + "\t sy:" + str(sy) + "\t sz:" + str(sz) +
        "\t rx:" + str(rx) + "\t ry:" + str(ry) + "\t rz:" + str(rz) +
        "\t px:" + str(px) + "\t py:" + str(py) + "\t pz:" + str(pz) )

    print("sx = {" + str(at[:,0,0]) + "}\n")
    """

    #print("rx = {" + str(at[:,1,0]) + "}\n")

    cFlags = 0 # Compression Flags
    bitsPerEntry = 0

    if sx.bitCount == -1 or sy.bitCount == -1 or sz.bitCount == -1 \
    or rx.bitCount == -1 or ry.bitCount == -1 or rz.bitCount == -1 \
    or px.bitCount == -1 or py.bitCount == -1 or pz.bitCount == -1:
        print("Compression Level too small to compress")
        return

    if hasScale:
        cFlags |= 0x01
        bitsPerEntry += sx.bitCount if not sx.constant else 0
        bitsPerEntry += sy.bitCount if not sy.constant else 0
        bitsPerEntry += sz.bitCount if not sz.constant else 0
    else:
        cFlags |= 0x02

    if hasRotation:
        cFlags |= 0x04
        bitsPerEntry += rx.bitCount if not rx.constant else 0
        bitsPerEntry += ry.bitCount if not ry.constant else 0
        bitsPerEntry += rz.bitCount if not rz.constant else 0
        bitsPerEntry += 1 #The 1 is for extra W rotation bit

    if hasPosition:
        cFlags |= 0x08
        bitsPerEntry += px.bitCount if not px.constant else 0
        bitsPerEntry += py.bitCount if not py.constant else 0
        bitsPerEntry += pz.bitCount if not pz.constant else 0

    # Compressed Header
    write_short(b, 0x04)
    write_short(b, cFlags)
    write_short(b, 160) # Not Hex in StudioSB
    write_ushort(b, bitsPerEntry)
    write_int(b, 204) # Not Hex in StudioSB
    write_int(b, len(nat.animationTrack))
    write_float(b, sx.min)
    write_float(b, sx.max)
    write_long64(b, sx.bitCount if hasScale else 16)
    write_float(b, sy.min)
    write_float(b, sy.max)
    write_long64(b, sy.bitCount if hasScale else 16)
    write_float(b, sz.min)
    write_float(b, sz.max)
    write_long64(b, sz.bitCount if hasScale else 16)
    write_float(b, rx.min)
    write_float(b, rx.max)
    write_long64(b, rx.bitCount if hasRotation else 16)
    write_float(b, ry.min)
    write_float(b, ry.max)
    write_long64(b, ry.bitCount if hasRotation else 16)
    write_float(b, rz.min)
    write_float(b, rz.max)
    write_long64(b, rz.bitCount if hasRotation else 16)
    write_float(b, px.min)
    write_float(b, px.max)
    write_long64(b, px.bitCount if hasPosition else 16)
    write_float(b, py.min)
    write_float(b, py.max)
    write_long64(b, py.bitCount if hasPosition else 16)
    write_float(b, pz.min)
    write_float(b, pz.max)
    write_long64(b, pz.bitCount if hasPosition else 16)
    dv = nat.animationTrack[0] #Default Values
    write_float(b, dv[0][0])
    write_float(b, dv[0][1])
    write_float(b, dv[0][2])
    write_float(b, dv[1][0])
    write_float(b, dv[1][1])
    write_float(b, dv[1][2])
    write_float(b, dv[1][3])
    write_float(b, dv[2][0])
    write_float(b, dv[2][1])
    write_float(b, dv[2][2])
    write_int(b, 0)

    # Now we can finally write the bits
    bitString = ""
    frame = 0
    for af in nat.animationTrack:
        if hasScale:
            #print("Frame: " + str(frame) + " af[0][0] = " + str(af[0][0]))
           # print("sx.quantanize = " + str(sx.quantanize(af[0][0], sx.bitCount)) + " ")
            bitString += get_bits(sx.quantanize(af[0][0], sx.bitCount), sx.bitCount)
            bitString += get_bits(sy.quantanize(af[0][1], sy.bitCount), sy.bitCount)
            bitString += get_bits(sz.quantanize(af[0][2], sz.bitCount), sz.bitCount)

        if hasRotation:
            #print("Frame: " + str(frame) + " af[1][0] = " + str(af[1][0]))
            #print("rx.quantanize = " + str(rx.quantanize(af[1][0], rx.bitCount)) + " ")
            bitString += get_bits(rx.quantanize(af[1][0], rx.bitCount), rx.bitCount)
            bitString += get_bits(ry.quantanize(af[1][1], ry.bitCount), ry.bitCount)
            bitString += get_bits(rz.quantanize(af[1][2], rz.bitCount), rz.bitCount)

        if hasPosition:
            bitString += get_bits(px.quantanize(af[2][0], px.bitCount), px.bitCount)
            bitString += get_bits(py.quantanize(af[2][1], py.bitCount), py.bitCount)
            bitString += get_bits(pz.quantanize(af[2][2], pz.bitCount), pz.bitCount)
            if not pz.constant:
                print("Frame: " + str(frame) + ", af[2][2] = " + str(af[2][2]) + ", pz.quantize = " + str(pz.quantanize(af[2][2], pz.bitCount))
                    + ",pz.bitCount =" + str(pz.bitCount) + ", bits = " + str(get_bits(pz.quantanize(af[2][2], pz.bitCount), pz.bitCount)))
        if hasRotation:
            # 'flip-W' bit
            w = math.sqrt(math.fabs( 1 - (
                rx.decompressed_value(af[1][0], rx.bitCount)**2 +
                ry.decompressed_value(af[1][1], ry.bitCount)**2 +
                rz.decompressed_value(af[1][2], rz.bitCount)**2)))
            fBit = 1 if (af[1][3] < 0) != (w < 0) else 0
            bitString += get_bits(fBit, 1)
        frame += 1

    #print("bitString Length = " + str(len(bitString)))
    #print("bitString = " + str(bitString))
    if bitString != "":
        ba = get_bytes(bitString)
        write_bytes(b, ba)

def get_bits(value, bitCount):
    bits = ""
    for i in range(bitCount):
        bit = (value >> i) & 0x1
        bits += format(bit, 'b')
    return bits

def get_bytes(bitString):
    ba = []
    byte = 0
    bitCounter = 0
    for bit in bitString:
        byte |= int(bit, 2) << bitCounter
        bitCounter += 1
        if bitCounter == 8:
            ba.append(byte)
            byte = 0
            bitCounter = 0
    if bitCounter != 0:
        ba.append(byte)
    return ba

"""
def write_transform(b, nat):
    if all_same(nat):
        write_const_transform(b, nat)
    else:
        write_compressed_transform(b, nat)
"""

def write_track_from_nat(b, nat, compression):
    nat.dataOffset = b.tell()
    nat.frameCount = len(nat.animationTrack)

    if ((nat.flags & 0x00ff) == AnimTrackFlags.Transform.value):
        if all_same(nat):
            write_const_transform(b, nat)
            nat.frameCount = 1
        elif compression:
            write_compressed_transform(b, nat)
        else:
            write_uncompressed_tranform(b, nat)

    elif ((nat.flags & 0x00ff) == AnimTrackFlags.Float.value):
        for af in nat.animationTrack:
            write_float(b,af)
        if (nat.frameCount == 1):
            nat.flags |= AnimTrackFlags.Constant.value
        else:
            nat.flags |= AnimTrackFlags.Direct.value

    elif ((nat.flags & 0x00ff) == AnimTrackFlags.Boolean.value):
        for af in nat.animationTrack:
            write_byte(b,af)
        if (nat.frameCount == 1):
            nat.flags |= AnimTrackFlags.Constant.value
        else:
            nat.flags |= AnimTrackFlags.Direct.value

    elif (nat.flags & 0x00ff) == AnimTrackFlags.Vector.value:
        for af in nat.animationTrack:
            for i in af: #[0, 1 , 2 , 3] Should be a vector of 4 values
                write_float(b, i)
        if (nat.frameCount == 1):
            nat.flags |= AnimTrackFlags.Constant.value
        else:
            nat.flags |= AnimTrackFlags.Direct.value

    nat.dataSize = b.tell() - nat.dataOffset
    pad(b, 0x64)

def gather_camera_groups(context):
    # Blender stuff
    sce = bpy.context.scene # Blender scene
    c = bpy.context.object # Blender Camera

    # Cameras have 2 groups, a "Transform" and a "Camera" group
    groups = []

    # Make Transform Group
    tg = Group()
    tg.nodesAnimType = AnimType.Transform.value

    # Make Transform Node
    tn = Node()
    tn.name = c.name

    # Make NodeAnimTrack
    tnat = tn.nodeAnimTrack
    for f in range(sce.frame_start, sce.frame_end):
        sce.frame_set(f)
        sx = c.scale[0]; sy = c.scale[1]; sz = c.scale[2]
        rw = c.rotation_quaternion[0] #Blender has RW in first index, Smash has it in last
        rx = c.rotation_quaternion[1]
        ry = c.rotation_quaternion[2]
        rz = c.rotation_quaternion[3]
        px = c.location[0]; py = c.location[1]; pz = c.location[2]
        tnat.animationTrack.append([[sx, sy, sz, 1], [rx, ry, rz, rw], [px, py, pz, 1]])
        tnat.flags |= AnimTrackFlags.Transform.value
        tnat.type = "Transform"

    tn.nodeAnimTrack = tnat
    tg.nodes.append(tn)

    # Make Camera Group
    cg = Group()
    cg.nodesAnimType = AnimType.Camera.value

    # Make Camera Node
    cn = Node()
    cn.name = c.name + "Shape"

    # Make Camera Subnodes as if it were material
    csnFarClip = Node()
    csnFieldOfView = Node()
    csnNearClip = Node()

    # FarClip seems to be the same value in all investigated tracks
    cnat = csnFarClip.nodeAnimTrack
    cnat.animationTrack.append(100000.0)
    cnat.flags |= AnimTrackFlags.Float.value
    cnat.flags |= AnimTrackFlags.Constant.value
    cnat.type = "FarClip"
    csnFarClip.nodeAnimTrack = cnat

    # Field of view changes throughout an animation, proper keyframing is planned
    cnat = csnFieldOfView.nodeAnimTrack
    cnat.flags |= AnimTrackFlags.Float.value
    cnat.type = "FieldOfView"
    for f in range(sce.frame_start, sce.frame_end):
        sce.frame_set(f)
        cnat.animationTrack.append(c["FOV"]) # Todo: Figure out FOV conversion, don't hardcode this value
    csnFieldOfView.nodeAnimTrack = cnat

    # NearClip seems to be the same value in all investigated tracks
    cnat = csnNearClip.nodeAnimTrack
    cnat.animationTrack.append(1.0)
    cnat.flags |= AnimTrackFlags.Float.value
    cnat.flags |= AnimTrackFlags.Constant.value
    cnat.type = "NearClip"
    csnNearClip.nodeAnimTrack = cnat

    cn.materialSubNodes.append(csnFarClip)
    cn.materialSubNodes.append(csnFieldOfView)
    cn.materialSubNodes.append(csnNearClip)

    cg.nodes.append(cn)

    groups.append(tg)
    groups.append(cg)
    return groups

def gather_groups(context):
    # Blender Setup
    obj = bpy.context.object
    sce = bpy.context.scene
    # Groups Setup
    groups = []
    # Make Transform group
    tg = Group()
    tg.nodesAnimType = AnimType.Transform.value
    for b in obj.pose.bones:
        if "_eff" in b.name:
            continue
        if "H_" in b.name:
            continue
        if "_offset" in b.name:
            continue
        if "_null" in b.name:
            continue
        tn = Node() #Transform Node
        tn.name = b.name
        nat = tn.nodeAnimTrack
        nat.flags |= AnimTrackFlags.Transform.value
        nat.type = "Transform"
        pfq = 0 # Previous Frame Quaternion
        for f in range(sce.frame_start, sce.frame_end):
            sce.frame_set(f)
            if not b.parent:
                t = b.matrix.to_translation()
                r = b.matrix.to_quaternion()
                if f != sce.frame_start:
                    if pfq.dot(r) < 0:
                        r.negate()  #fix for quaternion interpolation
                s = b.matrix.to_scale()
                nat.animationTrack.append([ [s[0], s[1], s[2], 1],
                                            [r[1], r[2], r[3], r[0]],
                                            [t[0], t[1], t[2], 1] ])
                pfq = r.copy()
            else:
                pmi = b.parent.matrix.inverted()
                rm = pmi @ b.matrix #"Relative Matrix", might rename this later
                t = rm.to_translation()
                r = rm.to_quaternion()
                if f != sce.frame_start:
                    if pfq.dot(r) < 0:
                        r.negate()
                s = rm.to_scale()
                nat.animationTrack.append([ [s[0], s[1], s[2], 1],
                                            [r[1], r[2], r[3], r[0]],
                                            [t[0], t[1], t[2], 1] ])
                pfq = r.copy()
        tn.nodeAnimTrack = nat
        tg.nodes.append(tn)
    tg.nodes.sort(key = lambda node: node.name)
    groups.append(tg)
    # Make Visibility Group
    vg = Group()
    vg.nodesAnimType = AnimType.Visibility.value
    allVisNames = [] #Keep track of completed visnames, only want to do one of each
    for child in obj.children:
        if("_VIS_O_" not in child.name):
            continue
        visName = child.name.split("_VIS_O_")[0]
        if visName in allVisNames:
            continue
        allVisNames.append(visName)
        n = Node()
        n.name = visName
        nat = n.nodeAnimTrack
        nat.flags |= AnimTrackFlags.Boolean.value
        nat.type = "Visibility"
        for f in range(sce.frame_start, sce.frame_end):
            sce.frame_set(f)
            isVisible = not child.hide_render
            nat.animationTrack.append(isVisible)
        n.nodeAnimTrack = nat
        vg.nodes.append(n)
    vg.nodes.sort(key = lambda node: node.name)
    groups.append(vg)

    # Make Material Group
    mg = Group()
    mg.nodesAnimType = AnimType.Material.value
    # Make Material Nodes and subnodes
    nodeNames = []
    for k, v in obj.items(): # Key, Value. Key Format for materials should be nat.name:nat.type
        if ":" not in k:
            continue
        nodeName = k.split(":")[0]
        if nodeName not in nodeNames:
            nodeNames.append(nodeName)
            node = Node()
            node.name = nodeName
            mg.nodes.append(node)
        msn = Node() # MaterialSubNode
        nodeType = k.split(":")[1]
        nat = msn.nodeAnimTrack
        if "Boolean" in nodeType:
            nat.flags |= AnimTrackFlags.Boolean.value
        elif "Float" in nodeType:
            nat.flags |= AnimTrackFlags.Float.value
        elif "Vector" in nodeType:
            nat.flags |= AnimTrackFlags.Vector.value
        else:
            print("Unknown nodeType: " + str(nodeType));
            continue
        nat.type = nodeType
        if "Vector" in nodeType:
            for f in range(sce.frame_start, sce.frame_end):
                sce.frame_set(f)
                nat.animationTrack.append([ v[0], v[1], v[2], v[3] ])
        else:
            for f in range(sce.frame_start, sce.frame_end):
                sce.frame_set(f)
                nat.animationTrack.append(v)
        msn.nodeAnimTrack = nat
        for node in mg.nodes:
            if node.name == nodeName:
                node.materialSubNodes.append(msn)

    groups.append(mg)

    return groups

def export_nuanmb_main(context, filepath, compression):
    print(str(filepath))
    fileName = os.path.basename(filepath)
    print(str(fileName))
    groups = []

    if (context.active_object.type == 'CAMERA'):
        compression = False # Smash Camera Anims are not compressed
        groups = gather_camera_groups(context)
    else:
        groups = gather_groups(context)

    animBuffer = make_anim_buffer(context, groups, compression)

    s = bpy.context.scene
    finalFrameIndex = s.frame_end - s.frame_start - 1

    with open(filepath, 'wb') as f:
        write_nuanmb(f, animBuffer, groups, finalFrameIndex, fileName)

    return {'FINISHED'}

# ==== Export OPERATOR ====
from bpy_extras.io_utils import ExportHelper

class NUANMB_Export_Operator(bpy.types.Operator, ExportHelper):
    """This appears in the tooltip of the operator and in the generated docs"""
    bl_idname = "export_scene.nuanmb"
    bl_label = "Export .nuanmb"

    # ExportHelper mixin class uses this
    filename_ext = ".nuanmb"

    filter_glob: bpy.props.StringProperty(
        default="*.nuanmb",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    # List of operator properties, the attributes will be assigned
    # to the class instance from the operator settings before calling.
    compression: bpy.props.BoolProperty(
        name="Enable Compression",
        description="Currently only compresses Transform tracks",
        default=True,
    )

    def execute(self, context):
        return export_nuanmb_main(context, self.filepath, self.compression)

    @classmethod
    def poll(self, context):
        if context.active_object is not None:
            if ((context.active_object.type == 'CAMERA') or (context.active_object.type == 'ARMATURE')):
                return True
        return False


# Only needed if you want to add into a dynamic menu
def menu_func_export(self, context):
    self.layout.operator(NUANMB_Export_Operator.bl_idname, text="NUANMB (.nuanmb)")


def register():
    bpy.utils.register_class(NUANMB_Export_Operator)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)


def unregister():
    bpy.utils.unregister_class(NUANMB_Export_Operator)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)


if __name__ == "__main__":
    register()

    # test call
    bpy.ops.export_test.some_data('INVOKE_DEFAULT')
