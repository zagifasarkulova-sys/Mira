from aiogram.fsm.state import State, StatesGroup


class MentorStates(StatesGroup):
    # Onboarding
    entering_name = State()
    entering_system_prompt = State()

    # Chat
    chatting = State()

    # Goals
    adding_goal = State()

    # Diary
    adding_diary = State()

    # Knowledge base
    adding_text_kb = State()

    # Image generation
    entering_image_prompt = State()

    # Settings
    editing_system_prompt = State()
