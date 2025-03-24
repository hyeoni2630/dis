import discord
from discord.ext import commands, tasks
import datetime
import pytz
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Channel IDs
REMINDER_CHANNEL_ID = 1305041229787959306
NICKNAME_CHANNEL_ID = 1331989813326385192
LINK_CHANNEL_ID = 1298225692776857701
IMAGE_CHANNEL_ID = 1298228940636291092
FACE_CHANNEL_1_ID = 1298228725594325012
FACE_CHANNEL_2_ID = 1298228896176541716
DIARY_CHANNEL_ID = 1312717054427795476
ROLE_CHANNEL_ID = 1322148577803505705

# Role IDs
GAME_ROLES = {
    "발로란트": 1322154373190778880,
    "마인크레프트": 1322154516761546824,
    "배틀그라운드": 1322154677709570069,
    "오버워치": 1322154739948982312,
    "스팀": 1322154861223088128,
    "기타게임": 1322158699225284628
}

STATUS_ROLES = {
    "커플": 1336603078316523581,
    "솔로": 1336604788321685504,
}

TOGGLE_ROLES = {
    "디코하자": 1336599444333789224
}

# List of channels that require image threads
IMAGE_THREAD_CHANNELS = [IMAGE_CHANNEL_ID, FACE_CHANNEL_1_ID, FACE_CHANNEL_2_ID]

class DiaryModal(discord.ui.Modal, title="오늘의 일기"):
    diary_content = discord.ui.TextInput(
        label="오늘의 일기를 작성해주세요",
        style=discord.TextStyle.paragraph,
        placeholder="오늘 하루는 어떠셨나요?",
        required=True,
        max_length=2000
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Get current KST time
        kst = pytz.timezone('Asia/Seoul')
        now = datetime.datetime.now(kst)
        date_str = now.strftime("%Y년 %m월 %d일")

        # Create diary embed
        embed = discord.Embed(
            title=f"📖 {interaction.user.display_name}님의 일기",
            description=self.diary_content.value,
            color=discord.Color.blue(),
            timestamp=now
        )
        embed.add_field(name="작성일", value=date_str, inline=False)
        embed.set_footer(text=f"작성자: {interaction.user.name}")

        # Send the diary entry and create a thread
        await interaction.response.send_message("일기가 작성되었습니다!", ephemeral=True)
        diary_message = await interaction.channel.send(
            embed=embed,
            view=DiaryManageButton(interaction.user.id)
        )
        
        # Create thread for the diary
        thread_name = f"💭 {date_str}의 이야기"
        thread = await diary_message.create_thread(name=thread_name, auto_archive_duration=1440)
        await thread.send(f"{interaction.user.mention}님의 하루에 대해 이야기를 나눠보세요!")

        # Delete old write diary button and send a new one
        async for message in interaction.channel.history(limit=10):
            if message.author == bot.user and any(component.label == "일기 쓰기" for component in message.components[0].children):
                await message.delete()
                break
        
        # Send new write diary button
        await send_diary_button(interaction.channel)

class EditDiaryModal(discord.ui.Modal, title="일기 수정하기"):
    def __init__(self, original_content: str):
        super().__init__()
        self.diary_content = discord.ui.TextInput(
            label="일기 내용",
            style=discord.TextStyle.paragraph,
            default=original_content,
            required=True
        )
        self.add_item(self.diary_content)

    async def on_submit(self, interaction: discord.Interaction):
        embed = interaction.message.embeds[0]
        embed.description = self.diary_content.value
        await interaction.message.edit(embed=embed)
        await interaction.response.send_message("✨ 일기가 수정되었습니다!", ephemeral=True)

class DiaryManageButton(discord.ui.View):
    def __init__(self, author_id: int):
        super().__init__(timeout=None)
        self.author_id = author_id

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.author_id:
            await interaction.response.send_message("자신의 일기만 수정/삭제할 수 있습니다!", ephemeral=True)
            return False
        return True

    @discord.ui.button(label="수정하기", style=discord.ButtonStyle.primary, emoji="✏️")
    async def edit_diary(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            original_content = interaction.message.embeds[0].description
            modal = EditDiaryModal(original_content)
            await interaction.response.send_modal(modal)
        except Exception as e:
            await interaction.response.send_message(f"모달 열기 중 오류가 발생했습니다: {str(e)}", ephemeral=True)

    @discord.ui.button(label="삭제하기", style=discord.ButtonStyle.danger, emoji="🗑️")
    async def delete_diary(self, interaction: discord.Interaction, button: discord.ui.Button):
        try:
            # Delete associated thread
            for thread in interaction.channel.threads:
                if thread.owner_id == interaction.message.id:
                    await thread.delete()
                    break
                    
            await interaction.message.delete()
            await interaction.response.send_message("일기가 삭제되었습니다!", ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"일기 삭제 중 오류가 발생했습니다: {str(e)}", ephemeral=True)

class DiaryButton(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="일기 쓰기", style=discord.ButtonStyle.primary, emoji="📝")
    async def diary_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(DiaryModal())

class RoleButton(discord.ui.Button):
    def __init__(self, role_id: int, label: str, emoji: str, style: discord.ButtonStyle, is_status: bool = False):
        super().__init__(label=label, emoji=emoji, style=style)
        self.role_id = role_id
        self.is_status = is_status

    async def callback(self, interaction: discord.Interaction):
        role = interaction.guild.get_role(self.role_id)
        if not role:
            await interaction.response.send_message("❌ 역할을 찾을 수 없습니다.", ephemeral=True)
            return

        if role in interaction.user.roles:
            await interaction.user.remove_roles(role)
            await interaction.response.send_message(
                f"```diff\n- {role.name} 역할이 제거되었습니다! 🗑️\n```",
                ephemeral=True
            )
        else:
            # For status roles, remove other status roles first
            if self.is_status:
                for status_role_id in STATUS_ROLES.values():
                    if status_role_id != self.role_id:
                        status_role = interaction.guild.get_role(status_role_id)
                        if status_role and status_role in interaction.user.roles:
                            await interaction.user.remove_roles(status_role)
            
            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                f"```diff\n+ {role.name} 역할이 추가되었습니다! ✨\n```",
                ephemeral=True
            )

class RoleView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
        # Game roles with custom colors
        self.add_item(RoleButton(GAME_ROLES["발로란트"], "발로란트", "🎮", discord.ButtonStyle.primary))
        self.add_item(RoleButton(GAME_ROLES["마인크레프트"], "마인크래프트", "⛏️", discord.ButtonStyle.success))
        self.add_item(RoleButton(GAME_ROLES["배틀그라운드"], "배그", "🔫", discord.ButtonStyle.danger))
        self.add_item(RoleButton(GAME_ROLES["오버워치"], "옵치", "🛡️", discord.ButtonStyle.primary))
        self.add_item(RoleButton(GAME_ROLES["스팀"], "스팀", "🎲", discord.ButtonStyle.success))
        self.add_item(RoleButton(GAME_ROLES["기타게임"], "기타게임", "🎯", discord.ButtonStyle.secondary))

class StatusView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)
        
        # Status roles with emojis (커플/솔로)
        self.add_item(RoleButton(STATUS_ROLES["커플"], "커플", "💑", discord.ButtonStyle.success, is_status=True))
        self.add_item(RoleButton(STATUS_ROLES["솔로"], "솔로", "🙋", discord.ButtonStyle.danger, is_status=True))
        # 디코하자 as a normal toggle role
        self.add_item(RoleButton(TOGGLE_ROLES["디코하자"], "디코하자", "🎧", discord.ButtonStyle.primary))

async def setup_role_channel(channel):
    # Clear existing messages
    async for message in channel.history(limit=10):
        await message.delete()

    # Send welcome message
    welcome_embed = discord.Embed(
        title="✨ 역할 선택하기 ✨",
        description="아래에서 원하는 역할을 선택해주세요!\n역할은 언제든지 변경할 수 있어요 💕",
        color=discord.Color.from_rgb(255, 182, 193)  # 파스텔 핑크
    )
    welcome_embed.set_footer(text="같은 버튼을 한 번 더 누르면 역할이 제거됩니다!")
    await channel.send(embed=welcome_embed)

    # Send game roles embed
    game_embed = discord.Embed(
        title="🎮 게임 역할 선택 🎮",
        description=(
            "```md\n"
            "# 게임 역할 안내 #\n"
            "* 여러 게임 역할을 동시에 가질 수 있어요!\n"
            "* 게임 친구를 쉽게 찾을 수 있어요 ⭐\n"
            "```\n"
            "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔"
        ),
        color=discord.Color.from_rgb(135, 206, 235)  # 하늘색
    )
    game_embed.set_footer(text="🎯 원하는 게임을 모두 선택해보세요!")
    await channel.send(embed=game_embed, view=RoleView())

    # Send divider
    divider_embed = discord.Embed(
        description="⋆｡ﾟ☁︎｡⋆｡ ﾟ☾ ﾟ｡⋆ ｡ﾟ☁︎｡⋆｡ﾟ",
        color=discord.Color.from_rgb(230, 230, 250)  # 라벤더
    )
    await channel.send(embed=divider_embed)

    # Send status roles embed
    status_embed = discord.Embed(
        title="💝 상태 역할 선택 💝",
        description=(
            "```md\n"
            "# 상태 역할 안내 #\n"
            "* 커플/솔로 중 하나만 선택할 수 있어요!\n"
            "* 다른 상태를 선택하면 이전 상태는 자동으로 제거돼요\n"
            "* 디코하자는 자유롭게 토글할 수 있어요 🎧\n"
            "```\n"
            "▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔▔"
        ),
        color=discord.Color.from_rgb(255, 192, 203)  # 분홍색
    )
    status_embed.set_footer(text="💫 현재 상태를 표시해보세요!")
    await channel.send(embed=status_embed, view=StatusView())

async def send_diary_button(channel):
    embed = discord.Embed(
        title="✨ 일기장",
        description="아래 버튼을 눌러 오늘의 일기를 작성해보세요!",
        color=discord.Color.blue()
    )
    await channel.send(embed=embed, view=DiaryButton())

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')
    # Set activity status to "총괄 갈구는 중"
    activity = discord.Activity(type=discord.ActivityType.playing, name="총괄 갈구는 중")
    await bot.change_presence(activity=activity)
    
    # Setup role channel
    role_channel = bot.get_channel(ROLE_CHANNEL_ID)
    if role_channel:
        await setup_role_channel(role_channel)
    
    # Send diary button in diary channel
    diary_channel = bot.get_channel(DIARY_CHANNEL_ID)
    if diary_channel:
        await send_diary_button(diary_channel)
    
    check_midnight.start()

@tasks.loop(minutes=1)
async def check_midnight():
    # Get current time in KST
    kst = pytz.timezone('Asia/Seoul')
    now = datetime.datetime.now(kst)
    
    # Check if it's midnight (00:00)
    if now.hour == 0 and now.minute == 0:
        channel = bot.get_channel(REMINDER_CHANNEL_ID)
        if channel:
            embed = discord.Embed(
                title="일일 추천 알림",
                description="@here /추천 한번씩 부탁드려요!!",
                color=discord.Color.blue()
            )
            await channel.send("@here", embed=embed)

@bot.event
async def on_message(message):
    # Ignore messages from the bot itself
    if message.author == bot.user:
        return

    # Handle link channel
    if message.channel.id == LINK_CHANNEL_ID:
        # Check if message contains a link
        has_link = any(url in message.content for url in ['http://', 'https://', 'www.'])
        
        if has_link:
            # Create thread for the link
            thread_name = f"💬 {message.author.display_name}의 링크 토론"
            thread = await message.create_thread(name=thread_name, auto_archive_duration=1440)
            await thread.send(f"{message.author.mention}님의 링크에 대해 이야기를 나눠보세요!")
        else:
            # Delete message and send warning
            await message.delete()
            warning = await message.channel.send(
                f"{message.author.mention} 이 채널에서는 링크만 공유할 수 있습니다. 링크에 대한 대화는 스레드에서 진행해주세요.",
                delete_after=5
            )

    # Handle image and face channels
    elif message.channel.id in IMAGE_THREAD_CHANNELS:
        if message.attachments and any(att.content_type and 'image' in att.content_type for att in message.attachments):
            # Create thread for the image
            # Use different emoji for face channels
            if message.channel.id in [FACE_CHANNEL_1_ID, FACE_CHANNEL_2_ID]:
                thread_name = f"👤 {message.author.display_name}의 얼공방"
            else:
                thread_name = f"🖼️ {message.author.display_name}의 이미지 토론"
            
            thread = await message.create_thread(name=thread_name, auto_archive_duration=1440)
            await thread.send(f"{message.author.mention}님의 이미지에 대해 이야기를 나눠보세요!")
        else:
            # Check if the message is not in a thread
            if not isinstance(message.channel, discord.Thread):
                # Delete message and send warning
                await message.delete()
                warning = await message.channel.send(
                    f"{message.author.mention} 이 채널에서는 이미지만 공유할 수 있습니다. 이미지에 대한 대화는 스레드에서 진행해주세요.",
                    delete_after=5
                )

    # Handle nickname changes
    elif message.channel.id == NICKNAME_CHANNEL_ID:
        if message.content.startswith('!닉'):
            try:
                # Split the message to get the new nickname
                new_nick = message.content[3:].strip()
                
                if not new_nick:
                    embed = discord.Embed(
                        title="❌ 닉네임 변경 실패",
                        description="새로운 닉네임을 입력해주세요.\n사용법: `!닉 [새로운 닉네임]`",
                        color=discord.Color.red()
                    )
                    embed.set_footer(text="올바른 형식으로 다시 시도해주세요.")
                    await message.channel.send(embed=embed)
                    return

                # Store the old nickname
                old_nick = message.author.display_name
                
                # Change the nickname
                await message.author.edit(nick=new_nick)
                
                # Create success embed with improved design
                embed = discord.Embed(
                    title="✅ 닉네임 변경 완료",
                    color=discord.Color.green()
                )
                embed.add_field(
                    name="이전 닉네임",
                    value=f"```{old_nick}```",
                    inline=True
                )
                embed.add_field(
                    name="현재 닉네임",
                    value=f"```{new_nick}```",
                    inline=True
                )
                embed.set_footer(text=f"요청자: {message.author.name}")
                await message.channel.send(embed=embed)
                
            except discord.Forbidden:
                embed = discord.Embed(
                    title="❌ 닉네임 변경 실패",
                    description="봇의 권한이 부족합니다.",
                    color=discord.Color.red()
                )
                embed.set_footer(text="서버 관리자에게 문의해주세요.")
                await message.channel.send(embed=embed)
            except Exception as e:
                embed = discord.Embed(
                    title="❌ 닉네임 변경 실패",
                    description="오류가 발생했습니다.",
                    color=discord.Color.red()
                )
                embed.set_footer(text="잠시 후 다시 시도해주세요.")
                await message.channel.send(embed=embed)
    
    await bot.process_commands(message)

# Run the bot
bot.run(TOKEN)
