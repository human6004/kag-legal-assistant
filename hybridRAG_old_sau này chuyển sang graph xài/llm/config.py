from dotenv import load_dotenv
import os
load_dotenv()

#Vay de linh hoat thay doi nhieu modfel khac trong tuong lai
#model cua google
LLM_PROVIDER = "gemini"
MODEL_NAME = "gemini-2.5-flash-lite"
API_KEY =os.getenv("GOOGLE_API_KEY")
