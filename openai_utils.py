# SPDX-FileCopyrightText: 2022-present deepset GmbH <info@deepset.ai>
#
# SPDX-License-Identifier: Apache-2.0

from typing import Dict

from haystack.dataclasses import ChatMessage


def _convert_message_to_openai_format(message: ChatMessage) -> Dict[str, str]:
    """
    Convert a message to the format expected by OpenAI's Chat API.

    See the [API reference](https://platform.openai.com/docs/api-reference/chat/create) for details.

    :returns: A dictionary with the following key:
        - `role`
        - `content`
        - `name` (optional)
    """
    openai_msg = {"role": message.role.value, "content": message.content}
    if message.name:
        openai_msg["name"] = message.name

    return openai_msg


Make an SQL insert statement to add a new user to our database. Name is [REDACTED_PERSON_1] Doe. Email is [REDACTED_EMAIL_ADDRESS_1] but also possible to contact him with [REDACTED_EMAIL_ADDRESS_2] email. Phone number is [REDACTED_PHONE_NUMBER_1] and the IP address is [REDACTED_IP_ADDRESS_1]. And credit card number is [REDACTED_CREDIT_CARD_RE_1]. He works in Test LLC.
