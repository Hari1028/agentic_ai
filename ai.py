import os
import autogen
from config import config_list  # ✅ Reuse your existing Azure config
from autogen import ConversableAgent, GroupChat, GroupChatManager

# ============================================================
# ⚙️ Define shared LLM config
# ============================================================
llm_config = {
    "config_list": config_list,
    "cache_seed": 42,
    "timeout": 120,
}

# ============================================================
# 🤖 Define Agents
# ============================================================

ingredient_agent = ConversableAgent(
    name="IngredientAgent",
    llm_config=llm_config,
    system_message="You are responsible for gathering ingredients for any cake requested.",
)
ingredient_agent.description = "Gather ingredients for the requested cake."

mixing_agent = ConversableAgent(
    name="MixingAgent",
    llm_config=llm_config,
    system_message="You mix all the ingredients provided into a batter.",
)
mixing_agent.description = "Mix ingredients to prepare cake batter."

baking_agent = ConversableAgent(
    name="BakingAgent",
    llm_config=llm_config,
    system_message="You bake the batter at the appropriate temperature.",
)
baking_agent.description = "Bake the cake batter in an oven."

decorating_agent = ConversableAgent(
    name="DecoratingAgent",
    llm_config=llm_config,
    system_message="You decorate the cake based on the requested flavor.",
)
decorating_agent.description = "Decorate the baked cake with relevant toppings."

tasting_agent = ConversableAgent(
    name="TastingAgent",
    llm_config=llm_config,
    system_message="You taste the final cake and give feedback.",
)
tasting_agent.description = "Taste the cake and provide the final review."

# ============================================================
# 🧁 Home Baker (Main initiator)
# ============================================================
home_baker_agent = ConversableAgent(
    name="HomeBakerAgent",
    llm_config=llm_config,
    system_message="You are a home baker trying to bake cakes with the help of other agents.",
)

# ============================================================
# 👥 Define GroupChat
# ============================================================
group_chat = GroupChat(
    agents=[
        ingredient_agent,
        mixing_agent,
        baking_agent,
        decorating_agent,
        tasting_agent,
    ],
    messages=[],
    max_round=6,
)

group_chat_manager = GroupChatManager(
    groupchat=group_chat,
    llm_config=llm_config,
)

# ============================================================
# 🗨️ Start Conversation
# ============================================================
print("\n🍰 Starting Cake-Baking GroupChat...\n")

chat_result = home_baker_agent.initiate_chat(
    group_chat_manager,
    message="I want to bake a chocolate cake.",
    summary_method="reflection_with_llm",
)

# ============================================================
# 📜 Log the Summary
# ============================================================
print("\n===== 🍫 Final Summary =====")
print(chat_result.summary)
