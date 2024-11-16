import sys
import time


from modules.util.configuration import getConfig
from modules.util.conversation import getConversation, getConversationName
from modules.util.conversation import writeConversation
from modules.util.model import getChatModelFormat, getChatModelPromptOverride
from modules.util.util import printError, printDebug, printResponse
from modules.util.util import getPromptHistoryFromConversation, addToPrompt
from modules.util.util import formatArrayToString, getServerResponseTokens
from modules.util.util import printPromptHistory
from modules.util.util import createOpenAITextRequest
from modules.util.util import createImageToTextRequest


# Add custom stopwords here as necessary
__stopwords = ["\n\n\n\n\n"] + getServerResponseTokens()


# SYSTEM prompt for web results
__strRespondUsingInformation = (
    "For your next response, "
    "use the following data:\n\n"
)


# SYSTEM prompt for input files, etc
__strRespondUsingInputFile = (
    "USER has provided the following file(s). "
    "For your next response, use the following data:\n\n"
)


# SYSTEM prompt for model switcher
__strDetermineBestAssistant = (
    "Use the following descriptions available assistants to determine "
    "which assistant possesses the most relevant skills related to the "
    "task and/or inquiry given by USER: "
)


#########################
""" BEGIN COMPLETIONS """
#########################


# Uses OpenAI API
def getTextToTextResponseStreamed(userPromptIn, seedIn, dataIn=[], fileIn=[], shouldWriteDataToConvo=False):
    if getConfig("default_text_to_text_model") is None:
        printError("\nChat output is disabled because the Text-to-Text model is not set.\n")
        return None

    chatFormat = getChatModelFormat(getConfig("default_text_to_text_model"))

    promptHistory = []

    if len(dataIn) > 0:
        promptHistory = addToPrompt(
            promptHistory,
            "system",
            __strRespondUsingInformation + formatArrayToString(dataIn, "\n\n"),
            chatFormat
        )

    if len(fileIn) > 0:
        promptHistory = addToPrompt(
            promptHistory,
            "system",
            __strRespondUsingInputFile + formatArrayToString(fileIn, "\n\n"),
            chatFormat
        )

    systemPromptOverride = getChatModelPromptOverride(
        getConfig("default_text_to_text_model")
    )

    if systemPromptOverride is not None:
        printDebug("\nUsing overridden system prompt.")
        promptHistory = addToPrompt(
            promptHistory,
            "system",
            systemPromptOverride,
            chatFormat
        )
    elif len(getConfig("system_prompt")) > 0:
        promptHistory = addToPrompt(
            promptHistory,
            "system",
            getConfig("system_prompt"),
            chatFormat
        )

    promptHistory = addToPrompt(
        promptHistory,
        "user",
        userPromptIn,
        chatFormat
    )

    printPromptHistory(promptHistory)

    data = {}
    data["model"] = getConfig("default_text_to_text_model")
    data["messages"] = promptHistory
    data["seed"] = seedIn
    completion = createOpenAITextRequest(data)

    printResponse("")
    if completion is not None:
        assistantResponse = ""
        pausedLetters = {}
        stop = False
        startTime = None
        try:
            for chunk in completion:  # L2
                letter = chunk.choices[0].delta.content
                if letter is not None:
                    if startTime is None:
                        startTime = time.perf_counter()
                    pause = False
                    for stopword in __stopwords:
                        if len(letter) >= 1 and stopword.startswith(letter):
                            if pausedLetters.get(stopword) is None:
                                pausedLetters[stopword] = ""
                    for stopword in list(pausedLetters.keys()):  # L3
                        index = len(pausedLetters[stopword])
                        if stopword[index] == letter:
                            pause = True
                            pausedLetters[stopword] += letter
                            if stopword in pausedLetters[stopword]:
                                printDebug(
                                    "\n\nStopping output because "
                                    "stopword reached: "
                                    "\"" + pausedLetters[stopword] + "\"\n"
                                )
                                stop = True
                                break  # L3
                    if len(pausedLetters) == 0:
                        pause = False
                    if not stop and not pause:
                        if len(pausedLetters) > 0:
                            longestPause = ""
                            for paused in list(pausedLetters.keys()):
                                pausedPhrase = pausedLetters[paused]
                                if len(longestPause) <= len(pausedPhrase):
                                    longestPause = pausedPhrase
                                del pausedLetters[paused]
                            printResponse(longestPause, "")
                            assistantResponse += longestPause
                        printResponse(letter, "")
                        time.sleep(0.005)
                        sys.stdout.flush()
                        assistantResponse += letter
                    elif stop:
                        break  # L2
            # break  # L1
        except Exception as e:
            printError("\n\nError occurred while parsing server output:\n")
            printError(str(e))
            return None
        endTime = time.perf_counter()
        printResponse("")

        if len(dataIn) > 0 and shouldWriteDataToConvo:
            writeConversation(
                getConversationName(),
                "SYSTEM: " + __strRespondUsingInformation + formatArrayToString(
                    dataIn, "\n\n"
                )
            )
        writeConversation(getConversationName(), "USER: " + userPromptIn)
        writeConversation(
            getConversationName(),
            "ASSISTANT: " + assistantResponse.replace(
                "ASSISTANT: ", ""
            ).replace("SYSTEM: ", ""))

        if startTime is not None and endTime is not None:
            totalTime = endTime - startTime
            responseLength = len(assistantResponse)
            charTime = responseLength / totalTime
            printDebug(
                f"\n{charTime:0.3f}chars/sec ("
                f"{responseLength}c/{totalTime:0.3f}s)"
            )

        return assistantResponse
    else:
        printError("\nNo response from server.")
        return None


def getImageToTextResponse(promptIn, filePathIn):
    response = createImageToTextRequest(promptIn, filePathIn)
    if response is not None:
        return response
    printError("\nNo response from server.")
    return None
