import json
import subprocess


from modules.file.operation import readFile
from modules.util.util import printDump, printError
from modules.util.util import createImageToTextRequest


def getImageText(filePath):
    return createImageToTextRequest("", filePath)


def getFileExtension(filePath):
    f = filePath.split(".")
    return f[len(f) - 1]


def getFileContents(filePath):
    fileExtension = getFileExtension(filePath)
    content = ""
    for entry, value in getFileMap().items():
        for ext in value:
            if fileExtension in ext:
                functionCall = entry
                content = functionCall(filePath)
                if content is not None and len(content) > 0:
                    return content
                else:
                    printError("\nFile content is none or empty.")
                    return None
    content = readFile(filePath, None)
    printDump("\n" + content)
    return content


# only support linux


def openLocalFile(filePath, shouldAsync, openerIn):
    if filePath is not None and len(filePath) > 0:
        if openerIn is None:
            opener = ["xdg-open"]
        else:
            if " " in openerIn:
                opener = openerIn.split(" ")
            else:
                opener = [openerIn]
        if shouldAsync:
            subprocess.Popen(opener + [filePath])
        else:
            subprocess.call(opener + [filePath])
    return


def loadJsonFromFile(filenameIn):
    return json.loads(readFile(filenameIn, None))


def getFileMap():
    return {
        getImageText: [
            "jpg",
            "jpeg",
            "png"
        ]
    }
