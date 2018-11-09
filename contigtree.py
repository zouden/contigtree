from mmap import mmap
import argparse
import sys
from collections import namedtuple
parser = argparse.ArgumentParser(description='''Generate a tree of contigs from a Minia contig file.
                                 Supply a search depth and one or more contig IDs (integers).
                                 This tool extracts the sequences of the target and connected contigs.
                                 Sequences are printed to stdout in FASTA format and the tree is printed to stderr.''')
parser.add_argument('filename', help='A contigs.fa file generated by Minia')
parser.add_argument('depth', type=int, help="Search depth / tree size. A value of 4 is suitable")
parser.add_argument('targets', type=int, nargs='+', help="Target contig IDs, separated by spaces")
args = parser.parse_args()

Segment = namedtuple("Segment", ['ID', 'flipped', 'seq', 'name', 'length'])


#%%
names = ["Albatross","Auklet","Bittern","Blackbird","Bluebird","Bunting","Chickadee","Cormorant","Cowbird","Crow","Dove",
         "Dowitcher","Duck","Eagle","Egret","Falcon","Finch","Flycatcher","Gallinule","Gnatcatcher","Godwit","Goldeneye",
         "Goldfinch","Goose","Grackle","Grebe","Grosbeak","Gull","Hawk","Heron","Hummingbird","Ibis","Jaeger","Jay","Junco",
         "Kingbird","Kinglet","Kite","Loon","Magpie","Meadowlark","Merganser","Murrelet","Nuthatch","Oriole","Owl","Pelican",
         "Petrel","Pewee","Phalarope","Phoebe","Pigeon","Pipit","Plover","Puffin","Quail","Rail","Raven","Redstart","Sandpiper",
         "Sapsucker","Scaup","Scoter","Shearwater","Shrike","Skua","Sparrow","Storm-Petrel","Swallow","Swift","Tanager","Teal",
         "Tern","Thrasher","Thrush","Titmouse","Towhee","Turnstone","Vireo","Vulture","Warbler","Wigeon","Woodpecker","Wren","Yellowlegs"]


def make_name(id):
    return names[id % len(names)]

#%%

class Segment:
    def __init__(self, ID, flipped, header, seq):
        self.ID = ID
        self.flipped = flipped
        self.header = header
        self.seq = seq
        self.length = len(seq)
        self.name = make_name(ID)

    def __str__(self):
        return f">{self.name}_{self.length}_{self.ID}\n{self.seq}"

    def __repr__(self):
        return f"{self.name}_{self.length}_{self.ID}"

def decode_fasta(m):
    ''' Reads a pair of lines from the current position '''
    header = m.readline().decode('utf-8').strip()
    seq = m.readline().decode('utf-8').strip()
    header_parts = header.split()
    if not header_parts[0].startswith('>'):
        raise ValueError("Malformed header line")
    line_ID = int(header_parts[0][1:])
    return line_ID, header, seq


def findleft(pos, m):
    ''' Returns the header+seq left of the current position '''
    m.seek(m.rfind(b'>', 0, pos))
    pos = m.tell()
    foundline, header, seq = decode_fasta(m)
    return pos, foundline, header, seq

  

def linehunter(target, filename): 
    ''' Finds a target ID (line number) in the FASTA file'''
#    print("looking for",target)
    f = open(filename, 'r+')
    m = mmap(f.fileno(), 0)
    jumps = 0
#    jumpto = len(m) ## find the last sequence
    pos, foundline, header, seq = findleft(len(m), m) ## find the last sequence
    while foundline != target:
        if 1 <= (target - foundline) < 10:
            #if we're close by, simply read some lines until we get there
            foundline, header, seq = decode_fasta(m)
#            print(jumps, "seeking", foundline)
        else:    
            #get an approximate position by assuming constant length of each line
            avglen = pos/foundline  
            pos, foundline, header, seq = findleft(int(target*avglen), m)
#            print(jumps, "jumping", avglen, foundline)
        jumps += 1
        if jumps>100:
            raise IndexError("Failed to find line", target)
    m.close()
    return pos, header, seq

# %%


def parse_link(text):
    bits = text.split(':')
    if len(bits) != 4:
        raise ValueError("Unable to parse link %s" % text)
    other = int(bits[2])
    reverse_this = bits[1] == '-'
    reverse_other = bits[3] == '-'
    return other, reverse_this, reverse_other


def reverse_complement(sequence):
    complement = str.maketrans('ATCGN', 'TAGCN')
    return sequence.translate(complement)[::-1]


def buildtree(filename, segments, ID, maxdepth=3, flip_flag=False, depth=0):
    ''' Main recursive function '''
    _, text, seq = linehunter(ID, filename)
    if flip_flag:
        seq = reverse_complement(seq)
    this_segment = Segment(ID, flip_flag, text, seq)
    print(f'\t|->{this_segment.name}_{this_segment.length}_{this_segment.ID}{"(r)" if flip_flag else ""}'.expandtabs(depth*10), file=sys.stderr)
    segments.append(this_segment)
    parts = text.split()
    if not parts[0].startswith('>'):
        raise ValueError("Malformed header line")
    branches = []
    link_data = [part for part in parts if part.startswith('L:')]
    if link_data and (depth < maxdepth):
        for link in link_data:
            other_ID, reverse_this, reverse_other = parse_link(link)
            if reverse_this == flip_flag:
                branches.append(buildtree(filename, segments, other_ID, maxdepth, reverse_other, depth=depth+1))
    return this_segment, tuple(branches)

if __name__ == '__main__':
    segments = []  # this list will be populated by the recursive function
    for target in args.targets:
        print(f' Tree forwards from {target} to depth {args.depth} '.center(80, '='), file=sys.stderr)
        buildtree(args.filename, segments, target, args.depth, flip_flag=False)
        print(f' Tree reverse from {target} to depth {args.depth} '.center(80, '='), file=sys.stderr)
        buildtree(args.filename, segments, target, args.depth, flip_flag=True)
    # make a dict of the segments to get only the unique ones
    segments = {segment.ID: segment for segment in segments}
    print(f' Unique contigs: {len(segments)} '.center(80, '='), file=sys.stderr)
    for segment in segments.values():
        print(segment)
