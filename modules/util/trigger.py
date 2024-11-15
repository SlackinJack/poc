import re


from modules.file.operation import folderExists, getPathTree
from modules.file.reader import getFileContents
from modules.util.configuration import getConfig
from modules.util.util import printDebug, printError, getStringMatchPercentage
from modules.util.util import startTimer, endTimer, errorBlankEmptyText
from modules.util.util import getFilePathFromPrompt, checkEmptyString
from modules.util.util import formatArrayToString
from modules.util.web import getYouTubeCaptions, getInfoFromWebsite


def checkTriggers(promptIn, seedIn, responseFuncIn):
    potentialTriggers = {}
    for key, value in getTriggerMap().items():
        for v in value:
            if v in promptIn:
                potentialTriggers[key] = getStringMatchPercentage(v, promptIn)
    if len(potentialTriggers) == 1:
        triggerToCall = list(potentialTriggers)[0]
        printDebug("\nCalling trigger: " + str(triggerToCall))
        startTimer(0)
        triggerToCall(responseFuncIn, promptIn, seedIn)
        endTimer(0)
        return True
    elif len(potentialTriggers) > 1:
        triggerToCall = None
        for trigger, percentage in potentialTriggers.items():
            if triggerToCall is None:
                triggerToCall = trigger
            elif percentage > potentialTriggers[triggerToCall]:
                triggerToCall = trigger
        if triggerToCall is not None:
            printDebug("\nCalling best-matched trigger: " + str(triggerToCall))
            startTimer(0)
            triggerToCall(responseFuncIn, promptIn, seedIn)
            endTimer(0)
            return True
    printDebug("\nNo triggers detected.")
    return False


def triggerOpenFile(responderIn, promptIn, seedIn):
    promptWithoutFilePaths = promptIn
    filePathsInPrompt = getFilePathFromPrompt(promptIn)
    fileContents = []
    detectedWebsites = []
    for filePath in filePathsInPrompt:
        if "/" in filePath:
            formattedFilePath = "'" + filePath + "'"
            if " " + formattedFilePath in promptWithoutFilePaths:
                promptWithoutFilePaths = promptWithoutFilePaths.replace(
                    " " + formattedFilePath,
                    ""
                )
            elif formattedFilePath + " " in promptWithoutFilePaths:
                promptWithoutFilePaths = promptWithoutFilePaths.replace(
                    formattedFilePath + " ",
                    ""
                )
            else:
                promptWithoutFilePaths = promptWithoutFilePaths.replace(
                    formattedFilePath,
                    ""
                )
            filePaths = []
            shouldUseFilePathsAsNames = False
            if folderExists(filePath):
                pathTree = getPathTree(filePath)
                filePaths = pathTree
                shouldUseFilePathsAsNames = True
                printDebug("\nOpening folder: " + filePath)
                printDebug("\nFiles in folder:")
                printDebug(formatArrayToString(pathTree, "\n"))
            else:
                filePaths = [filePath]
            for f in filePaths:
                fullFileName = f.split("/")
                fileName = fullFileName[len(fullFileName) - 1]
                printDebug("\nParsing file: " + fileName)
                fileContent = getFileContents(f)
                if fileContent is not None:
                    if checkEmptyString(fileContent):
                        fileContent = errorBlankEmptyText("file")
                    else:
                        if not getConfig("enable_internet"):
                            printDebug(
                                "\nInternet is disabled - "
                                "skipping embedded website check."
                            )
                        else:
                            # check for websites in file
                            words = re.split(
                                " |\n|\r|\)|\]|\}|\>",
                                fileContent
                            )
                            for word in words:
                                if word.startswith("http://") or (
                                    word.startswith("https://")
                                ):
                                    detectedWebsites.append(word)
                                    printDebug(
                                        "\nFound website in file:"
                                        " " + word + "\n"
                                    )
                    if shouldUseFilePathsAsNames:
                        fileContents.append(
                            "\n``` File \"" + f + "\""
                            "\n" + fileContent + "\n```\n"
                        )
                    else:
                        fileContents.append(
                            "\n``` File \"" + fileName + "\""
                            "\n" + fileContent + "\n```\n"
                        )
                    if len(detectedWebsites) > 0:
                        for website in detectedWebsites:
                            youtubeResult = checkForYoutube(website)
                            if youtubeResult is not None:
                                websiteTitle = "YouTube Video"
                                websiteText = youtubeResult
                            else:
                                web = getInfoFromWebsite(website, True, 0)
                                websiteTitle = web[1]
                                websiteText = web[2]
                                if not checkEmptyString(websiteText):
                                    printDebug(
                                        "\nRetrieved text from " + website + ""
                                        ": " + websiteText + "\n"
                                    )
                            if shouldUseFilePathsAsNames:
                                fileContents.append(
                                    "\n``` Website in file \"" + f + "\" "
                                    "[" + websiteTitle + " (" + website + ")]"
                                    "\n" + websiteText + "\n```\n"
                                )
                            else:
                                fileContents.append(
                                    "\n``` Website in file \"" + fileName + ""
                                    "\" [" + websiteTitle + " (" + website + ""
                                    ")]\n" + websiteText + "\n```\n"
                                )
                else:
                    printError("\nCannot get file contents.\n")
                    return None
        else:
            printDebug(
                "\nSkipped \"" + filePath + "\" because it did not "
                "contain \"/\" - assuming invalid file path."
            )
    return responderIn(
        promptWithoutFilePaths,
        seedIn=seedIn,
        fileIn=fileContents,
        shouldWriteDataToConvo=True
    )


def getTriggerMap():
    return {
        triggerOpenFile: [
            "'/"
        ]
    }
