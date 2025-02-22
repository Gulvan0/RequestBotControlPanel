from functools import partial
from tkinter import messagebox, Text, Tk, ttk, BooleanVar
from tkinter.constants import CENTER, END, LEFT, TOP

import jinja2

from apps_script import AppsScriptApiWrapper, AppsScriptFunction
from common_types import BroadcastInfo, Language, OpenRequest, SendType
from component_builder import BasicText, build_button, build_horizontal_centered_frame, build_image, build_option_row, build_tabs, ReadOnlyText
from gd import get_level, LevelGrade, RequestedDifficulty
from google_auth import get_credentials
from caretaker import Caretaker
from request_bot import construct_message_payload, construct_request_creation_payload, construct_request_pre_approval_payload, construct_request_resolution_payload, Request, RequestBotApiEndpoint, RequestBotApiWrapper, RequestBotRouteID
from yt import YoutubeApiWrapper

import sv_ttk
import twitch


def normalize_bot_request(request_from_bot_api: Request) -> OpenRequest | None:
    level = get_level(request_from_bot_api.level_id)
    if not level:
        return None

    return OpenRequest(
        submission_timestamp=request_from_bot_api.requested_at,
        language=Language.from_bot_api_value(request_from_bot_api.language),
        level_name=level.name,
        creator=level.author_name,
        level_id=request_from_bot_api.level_id,
        stars=level.stars_requested,
        difficulty=RequestedDifficulty.from_stars(level.stars_requested).value if level.stars_requested else "Unrated",
        showcase_link=request_from_bot_api.yt_link
    )


class Application:
    def get_current_broadcast(self) -> BroadcastInfo | None:
        yt_video_id = self.youtube.get_live_stream_video_id(self.caretaker.youtube_channel_id)
        if yt_video_id:
            return BroadcastInfo(yt_video_id, True)
        twitch_stream_id = twitch.get_stream_id(self.caretaker.twitch_login)
        if twitch_stream_id:
            return BroadcastInfo(twitch_stream_id, False)
        return None

    def save_settings(self) -> None:
        self.caretaker.api_root_url = self.api_root_url_entry.get_text()
        self.caretaker.api_token = self.token_entry.get_text()
        self.caretaker.youtube_channel_id = self.youtube_channel_id_entry.get_text()
        self.caretaker.twitch_login = self.twitch_login_entry.get_text()
        self.caretaker.form_link = self.form_link_entry.get_text()
        self.caretaker.spreadsheet_link = self.spreadsheet_link_entry.get_text()
        self.caretaker.start_announcement_text = self.start_announcement_text_entry.get_text()
        self.caretaker.end_goodbye_text = self.end_goodbye_text_entry.get_text()
        self.caretaker.api_root_url = self.api_root_url_entry.get_text()

        self.caretaker.save()

        self.request_bot.root_url = self.caretaker.api_root_url
        self.request_bot.token = self.caretaker.api_token

    def on_tab_changed(self, event) -> None:
        if event.widget.tab('current')['text'] != 'Options':
            self.save_settings()

    def on_exit(self, _) -> None:
        if self.destroyed:
            return
        self.save_settings()
        self.destroyed = True

    # TODO: Account for exceptions in all external service interactions, act accordingly (warn and ask for a manual action or require a restart)
    def perform_stream_startup_routine(self) -> None:
        self.app_script.execute_function(AppsScriptFunction.REOPEN_FORM)

        substitutions = dict(
            video_link=self.video_link,
            form_link=self.caretaker.form_link,
            spreadsheet_link=self.caretaker.spreadsheet_link
        )
        announcement_text = jinja2.Template(self.caretaker.start_announcement_text).render(substitutions)

        self.request_bot.post(
            endpoint=RequestBotApiEndpoint.SEND_MESSAGE,
            payload=construct_message_payload(
                text=announcement_text,
                target_route_id=RequestBotRouteID.START_ANNOUNCEMENT
            )
        )

        if self.yt_live_chat_id:
            self.youtube.post_message_to_live_chat(self.yt_live_chat_id, self.caretaker.form_link)
        else:
            self.resend_form_link_btn.config(state='disabled')

    def shift_to_stream_layout(self) -> None:
        if self.current_broadcast.is_youtube:
            self.video_link = f"https://www.youtube.com/watch?v={self.current_broadcast.video_id}"
            self.yt_live_chat_id = self.youtube.get_live_chat_id(self.current_broadcast.video_id)
        else:
            self.video_link = f"https://www.twitch.tv/{self.caretaker.twitch_login}"
            self.yt_live_chat_id = None

        self.start_stream_btn.pack_forget()
        self.streaming_mode_frame.pack(side=TOP, expand=True, fill='both')

    def on_start_stream_pressed(self) -> None:
        self.current_broadcast = self.get_current_broadcast()

        if self.current_broadcast:
            self.shift_to_stream_layout()
            if self.current_broadcast != self.caretaker.get_last_broadcast_info():
                self.perform_stream_startup_routine()
                self.caretaker.last_stream_id = self.current_broadcast.video_id
                self.caretaker.last_stream_is_youtube = self.current_broadcast.is_youtube
                self.caretaker.last_stream_processed_levels = set()
                self.caretaker.save()
        else:
            messagebox.showerror(None, "There is no active livestream on the selected channel. Did you specify channel ID in the Options tab correctly?")

    def on_end_stream_pressed(self) -> None:
        self.app_script.execute_function(AppsScriptFunction.CLOSE_FORM)

        dump = self.dump_remaining_requests_var.get()
        requests = self.app_script.close_remaining_requests(dump)

        if dump:
            self.process_new_responses()

            self.request_bot.post(
                RequestBotApiEndpoint.CREATE_REQUEST_BATCH,
                [
                    construct_request_creation_payload(request, self.video_link)
                    for request in requests
                    if request.level_id != self.current_level_id
                ]
            )

        self.request_bot.post(
            endpoint=RequestBotApiEndpoint.SEND_MESSAGE,
            payload=construct_message_payload(
                text=self.caretaker.end_goodbye_text,
                target_route_id=RequestBotRouteID.END_GOODBYE
            )
        )

        self.root.destroy()

    def pick_new_request(self) -> bool:
        self.process_new_responses()

        pick_oldest = self.pick_oldest_var.get()
        picked_request = self.app_script.pick_open_request(pick_oldest)
        is_from_bot = False
        self.current_request_id = None
        if not picked_request:
            bot_request = self.request_bot.pick_request(pick_oldest)
            self.current_request_id = bot_request.id
            is_from_bot = True
            picked_request = normalize_bot_request(bot_request) if bot_request else None
        if not picked_request:
            messagebox.showerror(None, "No requests yet!")
            return False

        self.current_level_id = picked_request.level_id

        if not self.current_request_id:
            self.current_request_id = self.request_bot.post(RequestBotApiEndpoint.CREATE_REQUEST, construct_request_creation_payload(picked_request, self.video_link))

        header = f"Request {self.current_request_id}"
        if is_from_bot:
            header += " (FROM BOT!)"

        if picked_request.stars:
            difficulty_explanation = f"requested {picked_request.stars} stars/moons"
        else:
            difficulty_explanation = "stars/moons were not requested"

        details_lines = [
            header,
            f"Language: {picked_request.language.get_spreadsheet_value()}",
            f"ID: {picked_request.level_id}",
            f"Level: {picked_request.level_name} by {picked_request.creator}",
            f"Difficulty: {picked_request.difficulty} ({difficulty_explanation})",
            f"Showcase: {picked_request.showcase_link or 'Not provided'}",
            f"Submitted: {picked_request.submission_timestamp}",
        ]

        self.request_details_entry.set_text("\n".join(details_lines))

        if self.alternate_var.get():
            self.pick_oldest_var.set(not pick_oldest)

        return True

    def on_pick_first_request_pressed(self) -> None:
        if self.pick_new_request():
            self.pick_first_request_btn.pack_forget()
            self.starrate_btn.pack(side=LEFT, padx=5)
            self.feature_btn.pack(side=LEFT, padx=5)
            self.epic_btn.pack(side=LEFT, padx=5)
            self.mythic_btn.pack(side=LEFT, padx=5)
            self.legendary_btn.pack(side=LEFT, padx=5)
            self.reject_btn.pack(side=LEFT, padx=5)
            self.later_btn.pack(side=LEFT, padx=5)

    def pick_next_request(self) -> None:
        if not self.pick_new_request():
            self.request_details_entry.set_text("Pick the request to continue")
            self.pick_first_request_btn.pack(side=LEFT)
            self.starrate_btn.pack_forget()
            self.feature_btn.pack_forget()
            self.epic_btn.pack_forget()
            self.mythic_btn.pack_forget()
            self.legendary_btn.pack_forget()
            self.reject_btn.pack_forget()
            self.later_btn.pack_forget()

    def on_opinion_btn_pressed(self, send_type: SendType) -> None:
        self.request_bot.post(
            endpoint=RequestBotApiEndpoint.RESOLVE_REQUEST,
            payload=construct_request_resolution_payload(
                request_id=self.current_request_id,
                sent_for=send_type,
                stream_link=self.video_link  # TODO: Use timecodes (if youtube)
            )
        )

        self.app_script.execute_function(AppsScriptFunction.RESOLVE_REQUEST, [self.current_level_id, send_type.get_apps_script_value()])

        self.pick_next_request()

    def on_later_pressed(self) -> None:
        self.request_bot.post(
            endpoint=RequestBotApiEndpoint.PRE_APPROVE_REQUEST,
            payload=construct_request_pre_approval_payload(
                request_id=self.current_request_id
            )
        )

        self.app_script.execute_function(AppsScriptFunction.RESOLVE_REQUEST, [self.current_level_id, "later"])

        self.pick_next_request()

    def on_resend_form_link_pressed(self) -> None:
        if self.yt_live_chat_id:
            self.youtube.post_message_to_live_chat(self.yt_live_chat_id, self.caretaker.form_link)

    def on_clear_queue_pressed(self) -> None:
        self.app_script.execute_function(AppsScriptFunction.REOPEN_FORM)

    # TODO: Account for exceptions in all external service interactions, act accordingly (warn and ask for a manual action or require a restart)
    def process_new_responses(self) -> None:
        rows = []
        for response in self.app_script.get_new_responses():
            if response.level_id in self.caretaker.last_stream_processed_levels:
                continue
            self.caretaker.last_stream_processed_levels.add(response.level_id)

            level = get_level(response.level_id)
            if not level or level.grade != LevelGrade.UNRATED:
                continue

            rows.append([
                response.submission_timestamp.isoformat(),
                response.language.value,
                level.name,
                level.author_name,
                str(response.level_id),
                str(level.stars_requested) if level.stars_requested else "NA",
                RequestedDifficulty.from_stars(level.stars_requested).value if level.stars_requested else "Unrated",
                response.showcase_link
            ])

        self.app_script.execute_function(AppsScriptFunction.APPEND_OPEN_REQUESTS, [rows])

        self.app_script.execute_function(AppsScriptFunction.CLEAR_NEW_RESPONSES)

        self.caretaker.save()

    def __init__(self) -> None:
        self.destroyed = False
        self.caretaker = Caretaker.load()

        self.current_broadcast = None  # Will be updated on the startup
        self.video_link = ""  # Will be defined once the "Start Stream" btn is pressed
        self.yt_live_chat_id = ""  # Will be defined once the "Start Stream" btn is pressed
        self.current_request_id = 0  # Will be defined once the first request is picked
        self.current_level_id = 0  # Will be defined once the first request is picked

        google_creds = get_credentials(client_secret_path="client_secret.json")
        self.app_script = AppsScriptApiWrapper(google_creds)
        self.youtube = YoutubeApiWrapper(google_creds)
        self.request_bot = RequestBotApiWrapper(self.caretaker.api_root_url, self.caretaker.api_token)

        self.root = Tk()

        self.root.title('Request Bot Control Panel')
        self.root.geometry('800x600')
        self.root.iconphoto(False, build_image("favicon"))

        self.tab_control = ttk.Notebook(self.root)

        self.stream_tab, self.options_tab, self.start_announcement_tab, self.end_goodbye_tab = build_tabs(self.tab_control, ['Stream', 'Options', 'Start Message', 'End Message'])

        self.start_stream_btn = ttk.Button(self.stream_tab, text="Start Stream", command=self.on_start_stream_pressed, state='disabled')
        self.start_stream_btn.place(relx=0.5, rely=0.5, anchor=CENTER)

        self.api_root_url_entry = build_option_row(self.options_tab, option_name='API Root URL', initial_value=self.caretaker.api_root_url)
        self.token_entry = build_option_row(self.options_tab, option_name='API Token', initial_value=self.caretaker.api_token, is_secret=True)
        self.youtube_channel_id_entry = build_option_row(self.options_tab, option_name='YouTube Channel ID', initial_value=self.caretaker.youtube_channel_id)
        self.twitch_login_entry = build_option_row(self.options_tab, option_name='Twitch Login', initial_value=self.caretaker.twitch_login)
        self.form_link_entry = build_option_row(self.options_tab, option_name='Form Link', initial_value=self.caretaker.form_link)
        self.spreadsheet_link_entry = build_option_row(self.options_tab, option_name='Spreadsheet Link', initial_value=self.caretaker.spreadsheet_link)

        self.start_announcement_text_entry = BasicText(self.start_announcement_tab, self.caretaker.start_announcement_text)
        self.start_announcement_text_entry.pack(side=LEFT, expand=True, fill='both')

        self.end_goodbye_text_entry = BasicText(self.end_goodbye_tab, self.caretaker.end_goodbye_text)
        self.end_goodbye_text_entry.pack(side=LEFT, expand=True, fill='both')

        self.streaming_mode_frame = ttk.Frame(self.stream_tab)

        self.end_stream_row = build_horizontal_centered_frame(self.streaming_mode_frame)
        self.end_stream_button = ttk.Button(self.end_stream_row, text="End Stream", command=self.on_end_stream_pressed)
        self.end_stream_button.pack(side=LEFT, padx=5)
        self.dump_remaining_requests_var = BooleanVar(value=True)
        self.dump_remaining_requests_checkbox = ttk.Checkbutton(self.end_stream_row, text="Dump remaining requests to bot", variable=self.dump_remaining_requests_var)
        self.dump_remaining_requests_checkbox.pack(side=LEFT, padx=5)

        self.request_picking_options_row = ttk.Frame(self.streaming_mode_frame)
        self.pick_oldest_var = BooleanVar(value=True)
        self.pick_randomly_radio_btn = ttk.Radiobutton(self.request_picking_options_row, text="Randomly", value=False, variable=self.pick_oldest_var)
        self.pick_randomly_radio_btn.pack(side=LEFT)
        self.pick_sequentially_radio_btn = ttk.Radiobutton(self.request_picking_options_row, text="In Sequence", value=True, variable=self.pick_oldest_var)
        self.pick_sequentially_radio_btn.pack(side=LEFT)
        self.alternate_var = BooleanVar(value=True)
        self.alternate_checkbox = ttk.Checkbutton(self.request_picking_options_row, text="Alternate", variable=self.alternate_var)
        self.alternate_checkbox.pack(side=LEFT)
        self.request_picking_options_row.pack(side=TOP, expand=True, fill='x')

        self.request_details_entry = ReadOnlyText(self.streaming_mode_frame, "Pick a request to start")
        self.request_details_entry.pack(side=TOP, expand=True, fill='both')

        self.request_actions_row = build_horizontal_centered_frame(self.streaming_mode_frame)
        self.pick_first_request_btn = ttk.Button(self.request_actions_row, text="Pick First Request", command=self.on_pick_first_request_pressed)
        self.pick_first_request_btn.pack(side=LEFT)
        self.starrate_btn = build_button(self.request_actions_row, "star", partial(self.on_opinion_btn_pressed, send_type=SendType.STARRATE))
        self.feature_btn = build_button(self.request_actions_row, "feature", partial(self.on_opinion_btn_pressed, send_type=SendType.FEATURE))
        self.epic_btn = build_button(self.request_actions_row, "epic", partial(self.on_opinion_btn_pressed, send_type=SendType.EPIC))
        self.mythic_btn = build_button(self.request_actions_row, "mythic", partial(self.on_opinion_btn_pressed, send_type=SendType.MYTHIC))
        self.legendary_btn = build_button(self.request_actions_row, "legendary", partial(self.on_opinion_btn_pressed, send_type=SendType.LEGENDARY))
        self.reject_btn = ttk.Button(self.request_actions_row, text="Reject", command=partial(self.on_opinion_btn_pressed, send_type=SendType.NOT_SENT))
        self.later_btn = ttk.Button(self.request_actions_row, text="Later", command=self.on_later_pressed)

        self.special_actions_row = build_horizontal_centered_frame(self.streaming_mode_frame)
        self.resend_form_link_btn = ttk.Button(self.special_actions_row, text="Resend Form Link", command=self.on_resend_form_link_pressed)
        self.resend_form_link_btn.pack(side=LEFT, padx=5)
        self.clear_queue_btn = ttk.Button(self.special_actions_row, text="Clear Queue", command=self.on_clear_queue_pressed)
        self.clear_queue_btn.pack(side=LEFT, padx=5)

        self.tab_control.pack(expand=True, fill='both')

        sv_ttk.set_theme("light")

        self.tab_control.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        self.root.bind('<Destroy>', self.on_exit)

    def on_startup(self) -> None:
        self.current_broadcast = self.get_current_broadcast()
        if self.current_broadcast and self.current_broadcast == self.caretaker.get_last_broadcast_info():
            self.shift_to_stream_layout()
        else:
            self.start_stream_btn.config(state='normal')

    def run(self) -> None:
        self.root.after(100, self.on_startup)  # noqa
        self.root.mainloop()


Application().run()