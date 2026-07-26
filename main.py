import asyncio
import json
import logging
from aiohttp import web
from aiokafka import AIOKafkaConsumer, AIOKafkaProducer
from config import Config

from agents.deepfake_agent import DeepfakeInspectorAgent
from agents.money_trail_agent import MoneyTrailAgent
from agents.aml_report_agent import AmlReportAgent

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

async def health_check(request):
    return web.json_response({"status": "ok", "service": "truetrace-agent-engine"})

async def consume_kyc(agent: DeepfakeInspectorAgent):
    consumer = AIOKafkaConsumer(
        Config.TOPIC_KYC_SUBMISSIONS,
        bootstrap_servers=Config.KAFKA_BOOTSTRAP,
        group_id=Config.KAFKA_GROUP_ID,
        auto_offset_reset="earliest"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            data = json.loads(msg.value.decode('utf-8'))
            await agent.analyze_kyc(data)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error in KYC consumer: {e}")
    finally:
        await consumer.stop()

async def consume_transactions(agent: MoneyTrailAgent):
    consumer = AIOKafkaConsumer(
        Config.TOPIC_TRANSACTIONS,
        bootstrap_servers=Config.KAFKA_BOOTSTRAP,
        group_id=Config.KAFKA_GROUP_ID,
        auto_offset_reset="earliest"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            data = json.loads(msg.value.decode('utf-8'))
            await agent.process_transaction(data)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error in Transactions consumer: {e}")
    finally:
        await consumer.stop()

async def consume_alerts(agent: AmlReportAgent):
    consumer = AIOKafkaConsumer(
        Config.TOPIC_ALERTS,
        bootstrap_servers=Config.KAFKA_BOOTSTRAP,
        group_id=Config.KAFKA_GROUP_ID,
        auto_offset_reset="earliest"
    )
    await consumer.start()
    try:
        async for msg in consumer:
            data = json.loads(msg.value.decode('utf-8'))
            if data.get('needs_str', False):
                await agent.generate_report(data)
    except asyncio.CancelledError:
        pass
    except Exception as e:
        logger.error(f"Error in Alerts consumer: {e}")
    finally:
        await consumer.stop()

async def start_kafka_producer():
    producer = AIOKafkaProducer(bootstrap_servers=Config.KAFKA_BOOTSTRAP)
    await producer.start()
    return producer

async def main():
    logger.info("Starting TrueTrace Multi-Agent Orchestrator...")
    
    # Init Kafka Producer
    producer = await start_kafka_producer()
    
    # Init Agents
    deepfake_agent = DeepfakeInspectorAgent(kafka_producer=producer)
    money_trail_agent = MoneyTrailAgent(kafka_producer=producer)
    aml_report_agent = AmlReportAgent(kafka_producer=producer)
    
    # Start Consumers
    tasks = [
        asyncio.create_task(consume_kyc(deepfake_agent)),
        asyncio.create_task(consume_transactions(money_trail_agent)),
        asyncio.create_task(consume_alerts(aml_report_agent))
    ]
    
    # Start HTTP Server for health check
    app = web.Application()
    app.router.add_get('/health', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8080)
    await site.start()
    logger.info("Health check server running on port 8080")
    
    try:
        await asyncio.gather(*tasks)
    except asyncio.CancelledError:
        logger.info("Shutting down...")
    finally:
        for t in tasks:
            t.cancel()
        await producer.stop()
        await runner.cleanup()

if __name__ == "__main__":
    try:
        import uvloop
        uvloop.install()
    except ImportError:
        pass
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user")
