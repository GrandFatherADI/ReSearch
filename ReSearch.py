import re
from datetime import datetime
from saleae.analyzers import HighLevelAnalyzer, AnalyzerFrame
from saleae.analyzers import NumberSetting, StringSetting
from saleae.data import GraphTimeDelta as GTD

kTimeZero = datetime(1, 1, 1)

def asNum(str):
    matches = re.findall("\d+", str)
    return int(matches[0])

def AsObj(**kargs): return type('', (object,), kargs)()


class StrBlockBuffer:
    def __init__(self, matchStr):
        self.blocks = []
        self.SetMatch(matchStr)

    def SetMatch(self, matchStr):
        self.pattern = matchStr

    def AddBlock(self, str, start_time, end_time):
        if not len(str):
            return

        charTime = float(end_time - start_time) / len(str)

        if len(self.blocks):
            lastBlock = self.blocks[-1]
            prevEnd = lastBlock.end

            if prevEnd + GTD(charTime / 2.0) >= start_time:
                # We can concatenate the new string onto the previous block
                lastBlock.str += str;
                lastBlock.end = end_time
                lastBlock.charTime = \
                    float(lastBlock.end - lastBlock.start) / len(lastBlock.str)
                return

        self.blocks.append(AsObj(
            str = str, start = start_time, end = end_time, charTime = charTime
            ))

    def Drop(self, lastIndex):
        # Remove all blocks up to the block containing lastIndex. Trim the
        # string in the block containing lastIndex to remove all characters
        # up to and including lastIndex.
        if not len(self.blocks):
            return

        # blockStartIndex is the index of first char in the current block wrt
        # the state of the blocks on entry.
        blockStartIndex = 0

        while len(self.blocks):
            block = self.blocks[0]
            strLen = len(block.str)

            if blockStartIndex > lastIndex:
                # Somehow we have passed lastIndex. Maybe it was bogus?
                # In any case, we are done.
                return

            if strLen + blockStartIndex <= lastIndex or not strLen:
                # This block doesn't contain lastIndex or lastIndex is the final
                # character in the block. In either case we drop the whole block
                blockStartIndex += len(block.str)
                del self.blocks[0]
                continue

            # The current block contains lastIndex somewhere before the end of
            # the string. Trim the string and update the block start time
            startEpoch = block.start
            endEpoch = block.end
            delChars = lastIndex - blockStartIndex
            block.start = startEpoch + GTD(block.charTime * delChars)
            block.str = block.str[lastIndex - blockStartIndex : ]
            return

    def DropBefore(self, timeDelta):
        # Remove all blocks before the end time of the last block - timeDelta
        if not len(self.blocks):
            return

        # Calculate the cut off time
        cutOffTime = self.blocks[-1].end - GTD(timeDelta)

        while len(self.blocks):
            block = self.blocks[0]
            strLen = len(block.str)

            if block.start > cutOffTime:
                # Whole block is within allowed time span. Done
                return

            if block.end < cutOffTime:
                # None of the block is within the allowed time span. Drop it.
                del self.blocks[0]
                continue

            # The block spans the start of the allowed time span. Trim the
            # block.
            delCount = int((float(cutOffTime - block.start) + block.charTime) / block.charTime)
            block.start += GTD(delCount * block.charTime)
            block.str = block.str[delCount : ]
            return

    def Match(self, drop = False):
        if not len(self.blocks):
            return

        searchStr = ""
        starts = []

        for block in self.blocks:
            startIndex = len(searchStr)
            endIndex = len(searchStr) + len(block.str)
            searchStr += block.str
            starts.append(AsObj(
                startIndex = startIndex,
                endIndex = endIndex,
                startTime = block.start,
                charTime = float(block.charTime)
            ))

        match = re.search(self.pattern, searchStr)

        if match is None:
            return None

        # Get first and last match indexs for the entire match
        firstIdx = match.start(0)
        lastIdx = match.end(0)

        for start in starts:
            if start.endIndex <= firstIdx:
                continue # Haven't reached the start block yet

            # This block's endIndex is greater than the index we are looking for
            # so the start must be in this block
            offset = firstIdx - start.startIndex
            startEpoch = start.startTime + GTD(offset * start.charTime)
            break

        # Set a fallback endEpoch value
        endEpoch = startEpoch + GTD(starts[-1].charTime)

        for start in starts:
            if start.endIndex < lastIdx:
                continue

            offset = lastIdx - start.startIndex
            endEpoch = start.startTime + GTD(offset * start.charTime)
            break

        result = AsObj(
            str = match.string[firstIdx:lastIdx],
            start = startEpoch, end = endEpoch
            )

        if drop:
            self.Drop(lastIdx)

        return result


class ReSearch(HighLevelAnalyzer):

    kMatch = StringSetting(label = "Match")
    kMatchTime = StringSetting(label = "Max span (s)")

    result_types = {
        "Matched": {"format": "{{{data.Matched}}}"},
        "bad": {"format": "{{{data.bad}}}"},
        }

    def Reset(self):
        self.startTime = None
        self.dataStart = None
        self.address = 0
        self.data = []

    ''' Utility routines
    '''

    def MakeFrame(self, start, stop, text):
        return AnalyzerFrame(self.device, start, stop, {self.device: text})

    def MakeListFrame(self, start, stop, list):
        listStr = ", ".join((str(item) for item in list))
        return AnalyzerFrame(self.device, start, stop, {self.device: listStr})


    ''' Logic2 API entry points and class construction
    '''

    def AddAddress(self, params):
        if bool == type(params.data["address"]):
            # Data is an address byte for an async serial protocol
            self.haveAddress = True

        if bytes != type(params.data["address"]):
            print("!AddAddress can't handle " + str(type(params.data["address"])))
            return False

        self.haveAddress = True
        asStr = "@" + hex(params.data["address"][0]) + " "
        self.blocks.AddBlock(asStr, params.start_time, params.end_time)
        return False

    def AddData(self, params):
        result = True

        if 'address' in params.data and params.data["address"]:
            asStr = '@' + hex(params.data["data"][0]) + ' '

        elif self.haveAddress or params.data["data"][0] > 127:
            # I2C or other bus protocol with addressed devices or the character
            # from an async serial analyzer is outside the ASCII range
            asStr = hex(params.data["data"][0]) + ' '
            result = False # Wait for a stop before we try to match

        else:
            asStr = params.data["data"].decode("ascii")

        self.blocks.AddBlock(asStr, params.start_time, params.end_time)
        return result

    def AddResult(self, params):
        self.blocks.AddBlock(params.data["data"], params.start_time, params.end_time)
        return True

    def AddStart(self, params):
        return False

    def AddStop(self, params):
        return True

    def __init__(self):
        self.blocks = StrBlockBuffer(self.kMatch)
        self.haveAddress = False
        self.isSource = False
        self.Reset()

        if not len(self.kMatchTime):
            self.kMatchTime = "0"

        self.kMatchTime = float(str(self.kMatchTime))

        # handlers return True if a match should be attempted
        self.handlerDispatch = {
            "address": self.AddAddress,
            "data": self.AddData,
            "result": self.AddResult,
            "start": self.AddStart,
            "stop": self.AddStop,
            }

    # Main Logic2 entry point
    def decode(self, newFrame: AnalyzerFrame):
        self.frame = newFrame

        if not newFrame.type in self.handlerDispatch:
            print("decode() can't handle " + newFrame.type)
            return

        if not self.handlerDispatch[newFrame.type](newFrame):
            return

        if self.kMatchTime:
            self.blocks.DropBefore(self.kMatchTime)

        match = self.blocks.Match(drop = True)

        if not match:
            return

        return AnalyzerFrame \
            ('Matched', match.start, match.end, {'Matched': match.str})
