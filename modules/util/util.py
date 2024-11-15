import base64
import datetime
import json
import openai
import random
import re
import readline  # unused, but fixes keyboard arrow keys for inputs
import requests
import time


from difflib import SequenceMatcher
from pynput import keyboard
from termcolor import colored  # https://pypi.org/project/termcolor/


from modules.file.operation import getFileFromURL, writeFileBinary, fileExists
from modules.util.configuration import getConfig
from modules.util.strings.endpoints import IMAGE_ENDPOINT, MODELS_ENDPOINT
from modules.util.strings.endpoints import TEXT_ENDPOINT


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


# TODO: Move this
__imagetotextSystemPrompt = (
    "You are a helpful ASSISTANT. "
    "Use the provided image to answer USER's inquiry."
)


__shouldInterruptCurrentOutputProcess = True


def setShouldInterruptCurrentOutputProcess(shouldInterrupt):
    global __shouldInterruptCurrentOutputProcess
    __shouldInterruptCurrentOutputProcess = shouldInterrupt
    return


def getShouldInterruptCurrentOutputProcess():
    return __shouldInterruptCurrentOutputProcess


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
    if getConfig("always_yes_to_yn"):
        return 0
    else:
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


def printCurrentSystemPrompt(systemPromptIn, printer, space):
    if len(systemPromptIn) > 0:
        printer(systemPromptIn + space)
    else:
        printer("(Empty)" + space)
    return


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


def getGrammarString(listIn):
    grammarStringBuilder = "root ::= ("
    for item in listIn:
        if len(grammarStringBuilder) > 10:
            grammarStringBuilder += " | "
        grammarStringBuilder += "\"" + item + "\""
    grammarStringBuilder += ")"
    return grammarStringBuilder


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


def setOrDefault(
    promptIn,
    defaultValueIn,
    verifierFuncIn,
    keepDefaultValueStringIn,
    setValueStringIn,
    verifierErrorStringIn
):
    return setOr(
        promptIn,
        "leave empty for current",
        defaultValueIn,
        verifierFuncIn,
        keepDefaultValueStringIn,
        setValueStringIn,
        verifierErrorStringIn
    )


def setOrPresetValue(
    promptIn,
    presetValueIn,
    verifierFuncIn,
    presetTypeStringIn,
    presetValueStringIn,
    verifierErrorStringIn
):
    return setOrPresetValueWithResult(
        promptIn,
        presetValueIn,
        verifierFuncIn,
        presetTypeStringIn,
        presetValueStringIn,
        "",
        verifierErrorStringIn
    )


def setOrPresetValueWithResult(
    promptIn,
    presetValueIn,
    verifierFuncIn,
    presetTypeStringIn,
    presetValueStringIn,
    verifiedResultStringIn,
    verifierErrorStringIn
):
    return setOr(
        promptIn,
        "leave empty for " + presetTypeStringIn,
        presetValueIn,
        verifierFuncIn,
        presetValueStringIn,
        verifiedResultStringIn,
        verifierErrorStringIn
    )


def setOr(
    messageIn,
    leaveEmptyMessageIn,
    valueIn,
    verifierFuncIn,
    noResultMessageIn,
    verifiedResultMessageIn,
    verifierErrorMessageIn
):
    printSeparator()
    result = printInput(
        messageIn + " (" + leaveEmptyMessageIn + " \"" + str(valueIn) + "\")"
    )
    printSeparator()
    if len(result) == 0:
        printRed("\n" + noResultMessageIn + ": " + str(valueIn) + "\n")
        return valueIn
    else:
        verifiedResult = verifierFuncIn(result)
        if verifiedResult[1]:
            if len(verifiedResultMessageIn) > 0:
                printGreen(
                    "\n" + verifiedResultMessageIn + ""
                    ": " + str(verifiedResult[0]) + "\n")
            return verifiedResult[0]
        else:
            printError(
                "\n" + verifierErrorMessageIn + ": " + str(valueIn) + "\n"
            )
            return valueIn


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


def createTextRequest(dataIn):
    # TODO: instruction and other supported functionality
    # data                                                    = {}
    # data["model"]                                           = modelIn
    # data["messages"]                                        = messagesIn
    # data["seed"]                                            = seedIn
    # if temperatureIn is not None:   data["temperature"]     = temperatureIn
    # if functionsIn is not None:     data["functions"]       = functionsIn
    # if functionCallIn is not None:  data["function_call"]   = functionCallIn
    # if grammarIn is not None:       data["grammar"]         = grammarIn

    # language              str
    # n                     int
    # top_p                 float
    # top_k                 float
    # max_tokens            int
    # echo                  bool
    # batch                 int
    # ignore_eos            bool
    # repeat_penalty        int/float
    # repeat_last_n         int/float
    # tfz                   ?
    # typical_p             ? (int/float)
    # rope_freq_base        int/float
    # rope_freq_scale       int/float
    # use_fast_tokenizer    bool
    # instruction           str
    # input                 ? (str)
    # stop                  ? (str)
    # mode                  int
    # backend               str
    # model_base_name       str

    result = sendCurlCommand(TEXT_ENDPOINT, dataIn=dataIn, returnResult=True)

    if result is not None:
        message = result["choices"][0]["message"]
        if "functions" not in dataIn:
            return cleanupServerResponseTokens(message["content"])
        else:
            try:
                functionCall = message["function_call"]
                if functionCall is not None and (
                    functionCall["arguments"] is not None
                ):
                    # might be broken
                    return json.loads(functionCall["arguments"])
                else:
                    printError(
                        "\nNo function/arguments received from server.\n"
                    )
            except Exception as e:
                printDebug("\nGetting function_call from message content.\n")
                printDebug("\n" + str(e))
                return json.loads(
                    cleanupServerResponseTokens(message["content"])
                )["arguments"]
    else:
        printError("\nNo response from the server.")
    return


def createImageToTextRequest(promptIn, filePathIn):
    if len(getConfig("default_image_to_text_model")) == 0:
        printError(
            "\nImg2Text is disabled because the Img2Text model is not set.\n"
        )
        return None

    if fileExists(filePathIn):
        with open(filePathIn, "rb") as f:
            fileExtension = filePathIn.split(".")
            fileExtension = fileExtension[len(fileExtension) - 1]
            systemMessageBody = {
                "role": "USER"
            }
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
            userMessageBody = {
                "role": "USER",
                "content": [
                    {
                        "type": "text", "text": promptIn
                    }
                ]
            }
            dataIn = {
                "model": getConfig("default_image_to_text_model"),
                "messages": [systemMessageBody, userMessageBody]
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


# Only used for streaming chat
def createOpenAITextRequest(dataIn):
    try:
        openai.api_key = "sk-xxx"
        openai.api_base = getConfig("address")
        return openai.ChatCompletion.create(
            model=dataIn["model"],
            messages=dataIn["messages"],
            seed=dataIn["seed"],
            stream=True,
            request_timeout=99999
        )
    except Exception as e:
        printError("\nError: " + str(e))
    return None
