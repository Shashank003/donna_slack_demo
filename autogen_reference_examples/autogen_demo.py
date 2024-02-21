import os
from dotenv import load_dotenv
import autogen
from typing import Annotated, Literal

CurrencySymbol = Literal["USD", "EUR"]

def exchange_rate(base_currency, quote_currency):
    if base_currency == quote_currency:
        return 1.0
    elif base_currency == "USD" and quote_currency == "EUR":
        return 1 / 1.1
    elif base_currency == "EUR" and quote_currency == "USD":
        return 1.1
    else:
        raise ValueError(f"Unknown currencies {base_currency}, {quote_currency}")
    
# need to register the functions
def currency_calculator(
    base_amount: Annotated[float, "Amount of currency in base_currency"],
    base_currency: Annotated[CurrencySymbol, "Base currency"] = "USD",
    quote_currency: Annotated[CurrencySymbol, "Quote currency"] = "EUR",
) -> str:
    quote_amount = exchange_rate(base_currency, quote_currency) * base_amount
    return f"{quote_amount} {quote_currency}"

def main():
    load_dotenv(override=True)
    config_list = [
        {
            "model": 'gpt-4-1106-preview',
            "api_key": os.environ["OPENAI_API_KEY"]
        }
    ]

    llm_config = {
        "config_list": config_list,
        "timeout": 120,
    }

    chatbot = autogen.AssistantAgent(
        name="chatbot",
        system_message="For currency exchange tasks, only use the functions you have been provided with. Reply TERMINATE when the task is done.",
        llm_config=llm_config,
    )

    # create a UserProxyAgent instance named "user_proxy"
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
        human_input_mode="NEVER",
        max_consecutive_auto_reply=10,
    )

    user_proxy.register_for_execution()(currency_calculator)
    chatbot.register_for_llm(description="Currency exchange calculator.")(currency_calculator)
    user_proxy.initiate_chat(
    chatbot,
    message="How much is 100 EUR?",
)



if __name__ == '__main__':
    main()

