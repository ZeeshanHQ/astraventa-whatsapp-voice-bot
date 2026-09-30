import asyncio
import json
import os
import websockets
from dotenv import load_dotenv

# Load env variables
load_dotenv()

async def test_dg():
    api_key = os.getenv("DEEPGRAM_API_KEY")
    # Using the exact URL we configured
    url = "wss://api.deepgram.com/v1/listen?encoding=mulaw&sample_rate=8000&channels=1&interim_results=true&endpointing=600&model=nova-2&smart_format=true"
    
    print(f"Connecting to Deepgram: {url}")
    headers = {"Authorization": f"Token {api_key}"}
    
    try:
        async with websockets.connect(url, additional_headers=headers) as ws:
            print("Successfully connected!")
            
            # Send 5 seconds of silence (null bytes for PCMU)
            # 1 second of PCMU G.711 is 8000 bytes. 
            # Silent byte in PCMU is 0xff.
            silence_chunk = b'\xff' * 160 # 20ms
            
            async def send_audio():
                for _ in range(100): # 2 seconds
                    await ws.send(silence_chunk)
                    await asyncio.sleep(0.02)
                print("Finished sending silence.")
                # Send CloseStream to Deepgram
                await ws.send(json.dumps({"type": "CloseStream"}))
            
            async def receive_responses():
                try:
                    async for message in ws:
                        data = json.loads(message)
                        print("Received message from Deepgram:", data)
                except Exception as e:
                    print("Error in receive:", e)
            
            await asyncio.gather(send_audio(), receive_responses())
            
    except Exception as e:
        print("Failed to connect or stream:", e)

if __name__ == "__main__":
    asyncio.run(test_dg())
