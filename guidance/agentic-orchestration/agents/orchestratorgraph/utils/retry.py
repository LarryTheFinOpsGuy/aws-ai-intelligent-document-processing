import asyncio
import logging
from utils.config import get_model

logger = logging.getLogger(__name__)

async def invoke_with_retry(agent, task, max_retries=5, **kwargs):
    """Invoke agent with retry and streaming exception handling"""
    def handle_exceptions(**cb_kwargs):
        if "serviceUnavailableException" in cb_kwargs or "throttlingException" in cb_kwargs:
            logger.warning("Service unavailable or throttling exception detected in stream")
            raise Exception("Service unavailable or throttled during streaming")
    
    agent.callback_handler = handle_exceptions
    
    for attempt in range(max_retries):
        try:
            # try a different model if the first one fails
            if attempt > 3:
                logger.warning(f"Retrying with different model. Attempt {attempt + 1} of {max_retries}")
                agent.model = get_model(model_name="nova_lite")
            return await agent.invoke_async(task, **kwargs)
        except Exception as e:
            if attempt < max_retries - 1:
                delay = 5 ** attempt
                logger.warning(f"Agent invoke attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
                await asyncio.sleep(delay)
            else:
                logger.warning(f"Agent invoke failed after {max_retries} attempts: {e}")
                raise
