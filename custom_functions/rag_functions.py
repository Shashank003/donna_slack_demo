from langchain_core.pydantic_v1 import BaseModel, Field
from langchain_core.tools import BaseTool
from typing import Any, Optional, Type
from langchain.tools.retriever import create_retriever_tool
from langchain.text_splitter import CharacterTextSplitter, RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_openai import OpenAIEmbeddings
from langchain_community.document_loaders import PyPDFLoader, TextLoader
import docx2txt


loader = TextLoader("./rag_tools_reference/acme_investment_policies.txt", autodetect_encoding=True)
documents = loader.load()
text_splitter = CharacterTextSplitter(chunk_size=1500, chunk_overlap=200)
texts = text_splitter.split_documents(documents)
embeddings = OpenAIEmbeddings()
db = FAISS.from_documents(texts, embeddings)

retriever = db.as_retriever()
retriever_tool = create_retriever_tool(
    retriever,
    "search_acme_investment_policies_document",
    "Searches and returns information about policies for Acme Investments",
)
retriever_tools_array = [retriever_tool]




