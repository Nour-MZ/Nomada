import openai

# Replace 'YOUR_API_KEY' with your actual OpenAI API key
openai.api_key = 'Sk-proj-ZxZ_osMCCCb6NAcWu319vH6bZPMna-xuLLNdY7wp4uRlSqOOP6Ib3GZG9cnxPkTkHGwKXhklcAT3BlbkFJey8yaw3SbxOhiKMoPjhRq3hlcVLFigKUKx6OiFfkwuFzib5vjo_pOiMQZx_CZAH3mEe8U0o8QA'

try:
    response = openai.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[{"role": "user", "content": "Hello, world!"}]
    )
    print("API key is valid. Response:", response.choices[0].message.content)
except openai.APIError as e:
    print(f"API key test failed: {e}")
except Exception as e:
    print(f"An unexpected error occurred: {e}")