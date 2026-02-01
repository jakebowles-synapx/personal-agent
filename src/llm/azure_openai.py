"""Azure OpenAI client using the Responses API for agentic capabilities."""

import json
from openai import AsyncOpenAI

from src.config import settings


class AzureOpenAIClient:
    """Client for Azure OpenAI using the Responses API (GPT-5 compatible)."""

    def __init__(self) -> None:
        # Responses API uses the /openai/v1/ endpoint path
        base_url = settings.azure_openai_endpoint.rstrip("/") + "/openai/v1/"

        self.client = AsyncOpenAI(
            base_url=base_url,
            api_key=settings.azure_openai_api_key,
        )
        self.deployment = settings.azure_openai_deployment

    async def chat(
        self,
        messages: list[dict],
        temperature: float = 0.7,
        max_output_tokens: int = 1000,
    ) -> str:
        """Send a response request and return the response content."""
        response = await self.client.responses.create(
            model=self.deployment,
            input=messages,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )
        return response.output_text or ""

    async def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        temperature: float = 0.7,
        max_output_tokens: int = 1000,
    ) -> dict:
        """Send a response request with tools and handle the agentic loop."""
        response = await self.client.responses.create(
            model=self.deployment,
            input=messages,
            tools=tools,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        # Extract tool calls from response output
        tool_calls = []
        text_content = ""

        for item in response.output:
            if item.type == "function_call":
                tool_calls.append({
                    "call_id": item.call_id,
                    "name": item.name,
                    "arguments": item.arguments,
                })
            elif item.type == "message":
                for content in item.content:
                    if content.type == "output_text":
                        text_content += content.text

        return {
            "content": text_content or response.output_text,
            "tool_calls": tool_calls if tool_calls else None,
            "response_id": response.id,
        }

    async def submit_tool_results(
        self,
        response_id: str,
        tool_results: list[dict],
    ) -> dict:
        """Submit tool results to continue the agentic loop."""
        # Build tool result items
        tool_outputs = []
        for result in tool_results:
            tool_outputs.append({
                "type": "function_call_output",
                "call_id": result["call_id"],
                "output": json.dumps(result["output"]) if not isinstance(result["output"], str) else result["output"],
            })

        response = await self.client.responses.create(
            model=self.deployment,
            previous_response_id=response_id,
            input=tool_outputs,
        )

        # Extract any further tool calls or final response
        tool_calls = []
        text_content = ""

        for item in response.output:
            if item.type == "function_call":
                tool_calls.append({
                    "call_id": item.call_id,
                    "name": item.name,
                    "arguments": item.arguments,
                })
            elif item.type == "message":
                for content in item.content:
                    if content.type == "output_text":
                        text_content += content.text

        return {
            "content": text_content or response.output_text,
            "tool_calls": tool_calls if tool_calls else None,
            "response_id": response.id,
        }
