from flask import Flask, jsonify, request, stream_with_context, Response
from flask_cors import CORS
from asgiref.wsgi import WsgiToAsgi
import gc
import json
import os
import time
from dotenv import load_dotenv

from mcp_use import MCPClient, MCPAgent
from langchain_openai import ChatOpenAI
from utilities.context_manager import AsyncLoopManager
from utilities.log_file import get_logger

logger = get_logger()

load_dotenv()
app = Flask(__name__)
CORS(app)

# asgi_app = WsgiToAsgi(app)

async_manager = AsyncLoopManager()

with open("configuration.json") as f:
    CONFIG = json.load(f)

client = MCPClient(config=CONFIG, allowed_servers=["test"])
prompt = """dont repeatedly execute tool after success response from each tool"""

llm = ChatOpenAI(
    model="gpt-4o",
    api_key=os.getenv("OPENAI_API_KEY"),
    streaming=True
)

@app.route("/", methods=["GET"])
def test():
    return jsonify({"welcome": "Working"})


@app.route("/api/chat", methods=["POST"])
def chat_session():
    data = request.get_json(silent=True) or {}
    query = request.args.get("query") or data.get("query", None)

    if not query:
        return jsonify({"error": "Cannot proceed further missing query params"})
    
    # STREAMING CODE:
    def generate():
        """Generator function for streaming response"""

        # Initialize to None for proper cleanup handling
        agent = None
        client = None

        try:
            # Create NEW MCPClient for each request
            client = MCPClient(config=CONFIG, allowed_servers=["math"])

            # Initialize client sessions in the persistent loop
            async def init_client():
                await client.create_all_sessions()

            async_manager.run(init_client())

            # Create agent using your existing function
            agent = MCPAgent(
                            llm=llm,
                            client=client,
                            max_steps=5,
                            api_key=os.getenv("OPENAI_API_KEY"),
                            system_prompt=prompt
                        )
            
            full_response = ""
            tool_counter = 0

            async def stream_agent():
                nonlocal full_response
                nonlocal tool_counter
                async for chunk in agent.stream(query, track_execution=False):
                    if type(chunk) is str:
                        chunk_text = chunk
                        full_response = chunk_text
                    else:
                        # Send each chunk to the UI
                        tool_counter += 1
                        chunk_text = chunk[1]
                        full_response += chunk_text
                        logger.info(f"chunk_text: {chunk_text}")

                        try:
                            parsed = json.loads(chunk_text)
                            resp = parsed.get("response", chunk_text)
                        except json.JSONDecodeError:
                            resp = chunk_text   # fallback to raw text

                        # Normalize LangChain TextContent
                        if isinstance(resp, list) and len(resp) > 0:
                            first = resp[0]
                            if isinstance(first, dict) and "text" in first:
                                tool_response = first["text"]
                            else:
                                tool_response = str(resp)
                        else:
                            tool_response = str(resp)


                        logger.info(f"final_tool_response: {tool_response}")
                        tool_output = json.dumps({
                                        "type": "tool_result",
                                        "tool": agent.tools_used_names[-1],
                                        "response": tool_response
                                    })

                        yield f"data: {tool_output}\n\n"
                        # time.sleep(10)

            # Use the persistent loop to run the async generator
            for chunk_data in async_manager.run_async_generator(stream_agent()):
                yield chunk_data

            tool_list = agent.tools_used_names
            logger.info(f"Tools called list = {agent.tools_used_names}")

            try:
                full_response = json.loads(full_response)["response"]
            except Exception as e:
                logger.info(f"API Exception in tool_response: {e}")
                if type(full_response) is not str:
                    full_response = str(full_response)

        except GeneratorExit:
            logger.info(f"Client disconnected")

        except Exception as e:
            logger.critical(f"Error in streaming: {str(e)}")
            yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
            

        finally:
            # ============ CLEANUP SECTION ============
            # Close agent and client in the SAME persistent loop they were created in

            async def cleanup():
                try:
                    if agent is not None:
                        await agent.close()
                        logger.debug(f"Agent closed")
                except Exception as e:
                    logger.error(f"Error closing agent: {str(e)}")

                try:
                    if client is not None:
                        await client.close_all_sessions()
                        logger.debug(f"MCP client closed")
                except Exception as e:
                    logger.error(f"Error closing client: {str(e)}")

            try:
                async_manager.run(cleanup())
            except Exception as e:
                logger.error(f"Error in cleanup: {str(e)}")

            # Clear references and garbage collect
            agent = None
            client = None
            gc.collect()

            logger.info(f"Cleanup completed")

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000, debug=True, use_reloader=False)

