import glob
import os
import urllib
from pathlib import Path


def fileExists(fileNameIn):
    return Path(fileNameIn).is_file()


def folderExists(folderNameIn):
    return Path(folderNameIn).is_dir()


def readFile(fileNameIn, splitter):
    if not fileExists(fileNameIn) and not folderExists(fileNameIn):
        writeFile(fileNameIn)
    with open(fileNameIn, "r") as f:
        theFile = f.read()
        if splitter is not None:
            theFile = theFile.split(splitter)
        return theFile


def writeFile(fileNameIn):
    if not fileExists(fileNameIn):
        open(fileNameIn, "w").close()
    return


def writeFileBinary(fileNameIn, dataIn):
    if not fileExists(fileNameIn):
        with open(fileNameIn, "wb") as f:
            f.write(dataIn)
    return


def appendFile(fileNameIn, dataIn):
    if not fileExists(fileNameIn):
        writeFile(fileNameIn)
    with open(fileNameIn, "a") as f:
        f.write(dataIn)
    return


def deleteFile(fileNameIn):
    if fileExists(fileNameIn):
        os.remove(fileNameIn)
    return


def deleteFilesWithPrefix(filePathIn, fileNamePrefixIn):
    files = os.listdir(filePathIn)
    for f in files:
        if f.startswith(fileNamePrefixIn):
            os.remove(filePathIn + f)
    return


def getFileFromURL(urlIn, folderIn):
    if urlIn is not None and len(urlIn) > 0:
        split = urlIn.split("/")
        fileName = split[len(split) - 1]
        fileName = "output/" + folderIn + "/" + fileName
        urllib.request.urlretrieve(urlIn, fileName)
        return fileName
    return None


def getPathTree(pathIn):
    fileTree = []
    for fileName in glob.glob(pathIn + "/**", recursive=True):
        if not folderExists(fileName) and fileExists(fileName):
            fileTree.append(fileName)
    return fileTree
