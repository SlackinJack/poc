import base64
import datetime
import json
import random
import re
import readline  # unused, but fixes keyboard arrow keys for inputs
import requests
import time


from difflib import SequenceMatcher
from termcolor import colored  # https://pypi.org/project/termcolor/


from modules.file.operation import fileExists
from modules.util.configuration import getConfig
from modules.util.strings.endpoints import MODELS_ENDPOINT
from modules.util.strings.endpoints import TEXT_ENDPOINT


__imagetotextSystemPrompt = (
    "Accurately estimate the size (in centimeters), "
    "and the weight (in grams), "
    "of the main subject in the image."
)


__grammarString = """root ::= ("Size: " number "cm by " number "cm by " number "cm, weight: " number "g")
number ::= [0-9]+["."]?[0-9]{1}"""


__serverResponseTokens = [
    "</s>",
    "<|end_of_sentence|>",
    "<|endoftext|>",
    "<|im_end|>",
    "<0x0A>"
]


def getServerResponseTokens():
    return __serverResponseTokens


__tic = time.perf_counter()
__tick = time.perf_counter()


####################
""" BEGIN PRINTS """
####################


def printInput(string):
    return input(string + ": ")


def printResponse(string, endIn="\n"):
    print(colored(string, "green"), end=endIn)
    return


def printGeneric(string, repeats=0):
    if repeats == 0:
        print(colored(string, "light_grey"))
    else:
        print(colored(string, "light_grey") * repeats)
    return


def printGreen(string):
    print(colored(string, "light_green"))
    return


def printRed(string):
    print(colored(string, "light_red"))
    return


def printError(string):
    print(colored(string, "red"))
    return


def printInfo(string):
    if getConfig("debug_level") >= 1:
        print(colored(string, "yellow"))
    return


def printDebug(string):
    if getConfig("debug_level") >= 2:
        print(colored(string, "light_grey"))
    return


def printDump(string):
    if getConfig("debug_level") >= 3:
        print(colored(string, "dark_grey"))
    return


def printSeparator():
    printGeneric("-", 64)
    return


def printPromptHistory(promptHistory):
    printDump("\nCurrent conversation:")
    for item in promptHistory:
        printDump("\n" + item["content"])
    return


def printSetting(isEnabled, descriptionIn):
    printGeneric(("[ON]  " if isEnabled else "[OFF] ") + descriptionIn)
    return


def clearWindow():
    printGeneric("\n", 64)
    return


# def printFormattedJson(jsonIn, printFunc=printDump):
#     printFunc(json.dumps(jsonIn, sort_keys=True, indent=4))
#     return


def printYNQuestion(messageIn):
    printSeparator()
    result = printInput(messageIn + " ([Y]es/[N]o/[E]xit)")
    printSeparator()
    result = result.lower()
    if "y" in result:
        return 0
    elif "e" in result:
        return 2
    else:
        return 1


def printMenu(titleIn, descriptionIn, choicesIn):
    printGeneric("\n" + titleIn + ":\n")
    if len(descriptionIn) > 0:
        printGeneric("\n" + descriptionIn + "\n")
    i = 0
    for c in choicesIn:
        printGeneric(" (" + str(i + 1) + ") " + c)
        i += 1
    printGeneric("\n (0) Exit\n")
    printSeparator()
    selection = printInput("Select item")
    escaped = False
    if "\"" in selection:
        escaped = True
        selection = selection.replace("\"", "")
    else:
        if selection == "0":
            selection = None
        else:
            result = intVerifier(selection)
            if result[1]:
                theResult = result[0] - 1
                if theResult <= len(choicesIn) - 1:
                    selection = choicesIn[theResult]
                else:
                    selection = ""
    printSeparator()
    if escaped:
        printGeneric("\nQuotes in input - escaped from numerical options.\n")
    return selection


########################
""" BEGIN STRING OPS """
########################


blankCharacters = ["\f", "\n", "\r", "\t", "\v"]


def checkEmptyString(strIn):
    if strIn is not None:
        blanks = blankCharacters + [" "]
        for s in strIn:
            if s not in blanks:
                return False
    return True


def cleanupString(stringIn):
    # remove all tabs, newlines, other special spaces
    for char in blankCharacters:
        out = stringIn.replace(char, " ")
    # remove all redundant spaces
    out = " ".join(out.split())
    # drop all non-ascii chars
    out = (out.encode("ascii", errors="ignore")).decode()
    return out


def cleanupServerResponseTokens(stringIn):
    for s in __serverResponseTokens:
        stringIn = stringIn.replace(s, "")
    return stringIn


def addToPrompt(prompt, role, content, chatFormat):
    match chatFormat:
        case "chatml":
            prompt.append({
                "role": role,
                "content": "<|im_start|>" + role + ""
                "\n" + content + "<|im_end|>"
            })
        case _:
            roleName = role.upper() + ": "
            prompt.append({
                "role": role,
                "content": roleName + content
            })
    return prompt


def trimTextBySentenceLength(textIn, maxLength):
    i = 0               # char position
    j = 0               # sentences
    k = 0               # chars since last sentence
    flag = False        # deleted a "short" sentence this run
    m = 24              # "short" sentence chars threshold
    for char in textIn:
        i += 1
        k += 1
        if (("!" == char) or ("?" == char) or ("." == char and (
            not textIn[i - 1].isnumeric() or (
                i + 1 <= len(textIn) - 1 and not textIn[i + 1].isnumeric()
            )
        ))):
            j += 1
            if k < m and not flag:
                j -= 1
                flag = True
            if j == maxLength:
                return textIn[0:i]
            k = 0
            flag = False
    return textIn


def formatArrayToString(arrayIn, separator):
    return separator.join(str(s) for s in arrayIn)


def getRoleAndContentFromString(stringIn):
    if len(stringIn) > 0:
        i = 0
        for s in stringIn:
            if ":" in s:
                return [stringIn[0:i], stringIn[i + 2:len(stringIn)]]
            else:
                i += 1
    if len(stringIn) > 0:
        printDebug(
            "\nThe following string is not in a valid role:content "
            "form: \"" + stringIn + "\"\n"
        )
    return


def errorBlankEmptyText(sourceIn):
    printError("The " + sourceIn + " is empty/blank!")
    return "The text received from the " + sourceIn + " is blank and/or empty."


def getRandomSeed():
    return random.randrange(1, (2 ** 32) - 1)


def getPromptHistoryFromConversation(conversationIn, chatFormat):
    promptHistory = []
    stringBuilder = ""
    for line in conversationIn:
        if line.startswith("SYSTEM: ") or (
            line.startswith("USER: ") or line.startswith("ASSISTANT: ")
        ):
            if len(stringBuilder) == 0:
                stringBuilder += line
            else:
                s = getRoleAndContentFromString(stringBuilder)
                if s is not None:
                    promptHistory = addToPrompt(
                        promptHistory,
                        s[0].lower(),
                        s[1],
                        chatFormat
                    )
                stringBuilder = line
        else:
            stringBuilder += line
    s = getRoleAndContentFromString(stringBuilder)
    if s is not None:
        promptHistory = addToPrompt(
            promptHistory,
            s[0].lower(),
            s[1],
            chatFormat
        )
    return promptHistory


def escapeJSONApostrophes(stringIn):
    return stringIn.replace("'", "\\'")


def removeApostrophesFromFileInput(stringIn):
    return stringIn.replace("' ", "").replace("'", "")


def getStringMatchPercentage(sourceStringIn, targetStringIn):
    return SequenceMatcher(None, sourceStringIn, targetStringIn).ratio() * 100


def getFilePathFromPrompt(stringIn):
    return (re.findall(r"'(.*?)'", stringIn, re.DOTALL))


########################
""" BEGIN MISC UTILS """
########################


def intVerifier(stringIn):
    try:
        return [int(stringIn), True]
    except:
        return [stringIn, False]


def floatVerifier(stringIn):
    try:
        return [float(stringIn), True]
    except:
        return [stringIn, False]


def getDateTimeString():
    return datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")


def startTimer(timerNumber):
    match timerNumber:
        case 0:  # foreground process timer
            global tic
            tic = time.perf_counter()
        case 1:  # tests timer
            global tick
            tick = time.perf_counter()
        case _:
            printError("\nUnknown start timer: " + str(timerNumber))
    return


def endTimer(timerNumber):
    toc = time.perf_counter()
    stringFormat = "\n"
    match timerNumber:
        case 0:
            stringFormat += f"Prompt processing time: {toc - tic:0.3f}"
        case 1:
            stringFormat += f"Test time: {toc - tick:0.3f}"
        case _:
            printError("\nUnknown end timer: " + str(timerNumber))
            return
    stringFormat += " seconds"
    printDebug(stringFormat)
    return


######################
""" BEGIN REQUESTS """
######################


def sendCurlCommand(
    endpointIn,
    dataIn=None,
    fileIn=None,
    returnResult=False,
    returnJson=True
):
    theAddress = getConfig("address").replace("/v1", "/")
    try:
        if dataIn is not None and dataIn.get("model") is not None:
            if not findModelFromServer(dataIn["model"]):
                printError("\nRequested model does not exist - aborting.")
                return None
        if dataIn is not None:
            result = requests.post(theAddress + endpointIn, json=dataIn)
        elif fileIn is not None:
            result = requests.post(theAddress + endpointIn, files=fileIn)
        else:
            result = requests.get(theAddress + endpointIn)

        plainResult = str(result)

        if plainResult == "<Response [200]>":
            if returnJson:
                resultJson = result.json()
                if "error" in resultJson is not None:
                    printError("\nError: " + resultJson["error"]["message"])
                    return
                elif returnResult:
                    return resultJson
                else:
                    # probably unused - included for redundancy
                    return json.loads(str(result.content, "utf-8"))
            else:
                return result.content
        elif plainResult == "<Response [404]>":
            printError(
                "\nResource cannot be found on the server - "
                "check the endpoint address.\n"
            )
        else:
            printError("\nError: " + plainResult)
            jsonError = json.loads(str(result.content, "utf-8"))
            if jsonError.get("error").get("message") is not None:
                errorMessage = jsonError["error"]["message"]
                printError("\n" + errorMessage)
            else:
                printError("\nResponse: " + str(jsonError))
    except Exception as e:
        printError(str(e))
        printError(
            "\nCannot send command to the server - check your connection."
        )
    return


def createImageToTextRequest(promptIn, filePathIn):
    if len(getConfig("default_image_to_text_model")) == 0:
        printError(
            "\nImg2Text is disabled because the Img2Text model is not set.\n"
        )
        return None

    if fileExists(filePathIn):
        fileExtension = filePathIn.split(".")
        fileExtension = fileExtension[len(fileExtension) - 1]
        systemMessageBody = {
            "role": "USER"
        }
        with open(filePathIn, "rb") as f:
            systemMessageBody["content"] = [
                {
                    "type": "text",
                    "text": __imagetotextSystemPrompt
                },
                {
                    "type": "image_url",
                    "image_url": {
                        "url": "data:image/" + fileExtension + ";base64," + ""
                        "" + base64.b64encode(f.read()).decode("utf-8")
                    }
                }
            ]
        dataIn = {
            "grammar": __grammarString,
            "model": getConfig("default_image_to_text_model"),
            "messages": [systemMessageBody],
        }

        result = sendCurlCommand(
            TEXT_ENDPOINT,
            dataIn=dataIn,
            returnResult=True
        )
        if result is not None:
            message = result["choices"][0]["message"]["content"]
            message = cleanupString(message)
            message = cleanupServerResponseTokens(message)
            return message
        else:
            printError("\nNo message from server!\n")
    else:
        printError("\nFile does not exist!\n")
    return None


def getModelsFromServer(silent):
    result = sendCurlCommand(MODELS_ENDPOINT, returnResult=True)
    if not silent:
        printDump("\n" + str(result))
    if result is not None and not checkEmptyString(result):
        return result["data"]
    else:
        printError("\nError getting model list.")
    return


def findModelFromServer(modelNameIn):
    models = getModelsFromServer(True)
    if models is not None:
        for model in models:
            if model["id"] == modelNameIn:
                return True
    return False
