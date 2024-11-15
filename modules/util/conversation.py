from modules.file.operation import appendFile, readFile, writeFile
from modules.util.strings.paths import CONVERSATIONS_FILE_PATH
from modules.util.util import getDateTimeString


__strConvoTimestamp = getDateTimeString()
__strConvoName = __strConvoTimestamp


def writeConversation(convoNameIn, strIn):
    appendFile(CONVERSATIONS_FILE_PATH + convoNameIn + ".convo", strIn + "\n")
    return


def getConversation(convoNameIn):
    return readFile(CONVERSATIONS_FILE_PATH + convoNameIn + ".convo", "\n")


def setConversation(fileNameIn):
    global __strConvoName
    writeFile(CONVERSATIONS_FILE_PATH + fileNameIn + ".convo")
    __strConvoName = fileNameIn
    return


def getConversationName():
    return __strConvoName
