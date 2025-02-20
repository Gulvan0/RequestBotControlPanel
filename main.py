from pathlib import Path
from tkinter import messagebox, Tk, ttk, BooleanVar
from tkinter.constants import CENTER, END, LEFT, TOP

import jinja2

from apps_script import AppsScriptApiWrapper, AppsScriptFunction
from component_builder import build_option_row, build_tabs
from gd import get_level, LevelGrade, RequestedDifficulty
from google_auth import get_credentials
from caretaker import Caretaker
from yt import YoutubeApiWrapper

import asyncio
import sv_ttk
import requests


class Application:
    def save_settings(self) -> None:
        self.caretaker.api_token = self.token_entry.get()
        self.caretaker.channel_id = self.channel_id_entry.get()
        self.caretaker.start_announcement_text = self.start_announcement_text_entry.get()
        self.caretaker.end_goodbye_text = self.end_goodbye_text_entry.get()
        self.caretaker.api_root_url = self.api_root_url_entry.get()
        self.caretaker.save()

    def on_tab_changed(self, event) -> None:
        if event.widget.tab('current')['text'] != 'Options':
            self.save_settings()

    def on_exit(self, _) -> None:
        if self.destroyed:
            return
        self.save_settings()
        self.destroyed = True

    # TODO: Account for exceptions in all external service interactions, act accordingly (warn and ask for a manual action or require a restart)
    def perform_stream_startup_routine(self, video_id: str) -> None:
        self.app_script.execute_function(AppsScriptFunction.REOPEN_FORM)

        substitutions = dict(
            video_link=self.video_link,
            form_link=self.caretaker.form_link,
            spreadsheet_link=self.caretaker.spreadsheet_link
        )
        announcement_text = jinja2.Template(self.caretaker.start_announcement_text).render(substitutions)

        requests.post(
            url=self.caretaker.api_root_url.removesuffix("/") + "/message/send",  # TODO: What if it's empty? Invalid? Account for those cases for every option, in every place it's used
            json=dict(
                text=announcement_text,
                target_route_id="stream_start_announcement"
            ),
            headers={
                "x-key": self.caretaker.api_token
            }
        )

        self.live_chat_id = self.youtube.get_live_chat_id(video_id)
        self.youtube.post_message_to_live_chat(self.live_chat_id, self.caretaker.form_link)

    def shift_to_stream_layout(self) -> None:
        self.start_stream_btn.pack_forget()
        self.streaming_mode_frame.pack(TOP, expand=True, fill='both')

    def on_start_stream_pressed(self) -> None:
        video_id = self.youtube.get_live_stream_video_id(self.caretaker.channel_id)

        if video_id:
            self.video_link = f"https://www.youtube.com/watch?v={video_id}"
            if video_id != self.caretaker.last_stream_id:
                self.perform_stream_startup_routine(video_id)
                self.caretaker.last_stream_id = video_id
                self.caretaker.last_stream_processed_levels = set()
                self.caretaker.save()
            self.shift_to_stream_layout()
        else:
            messagebox.showerror(None, "Not found")

    def on_end_stream_pressed(self) -> None:
        self.app_script.execute_function(AppsScriptFunction.CLOSE_FORM)

        response = self.app_script.execute_function(AppsScriptFunction.CLOSE_REMAINING_OPEN_REQUESTS, [self.dump_remaining_requests_var.get()])
        result = response['response']['result']

        ...  # TODO: Fill (parse result and batch create via bot API - maybe move parsing to apps_script module)

        requests.post(
            url=self.caretaker.api_root_url.removesuffix("/") + "/message/send",
            json=dict(
                text=self.caretaker.end_goodbye_text,
                target_route_id="stream_end_goodbye"
            ),
            headers={
                "x-key": self.caretaker.api_token
            }
        )

        self.root.destroy()

    def pick_new_request(self) -> bool:
        ...  # TODO: Fill. First, process new responses. Pick from bot API if no level was requested on stream. Use is_random_var. Update request_info_entry text. Set current_request_id and current_level_id. If 0 requests, show messagebox and return False

        if self.alternate_var.get():
            self.is_random_var.set(not self.is_random_var.get())

        return True

    def on_pick_first_request_pressed(self) -> None:
        if self.pick_new_request():
            self.pick_first_request_btn.pack_forget()
            self.approve_btn.pack(LEFT)  # TODO: Replace with 5 approval icon buttons
            self.reject_btn.pack(LEFT)
            self.later_btn.pack(LEFT)

    def on_approve_pressed(self) -> None:
        requests.post(
            url=self.caretaker.api_root_url.removesuffix("/") + "/request/resolve",
            json=dict(
                request_id=self.current_request_id,
                sent_for=...,  # TODO: Fill
                stream_link=self.video_link  # TODO: Use timecodes
            ),
            headers={
                "x-key": self.caretaker.api_token
            }
        )

        self.app_script.execute_function(AppsScriptFunction.RESOLVE_REQUEST, [self.current_level_id, "approved"])  # TODO: Send concrete SendType, process it on App Script side

        self.pick_new_request()

    def on_reject_pressed(self) -> None:
        requests.post(
            url=self.caretaker.api_root_url.removesuffix("/") + "/request/resolve",
            json=dict(
                request_id=self.current_request_id,
                sent_for=None,
                stream_link=self.video_link  # TODO: Use timecodes
            ),
            headers={
                "x-key": self.caretaker.api_token
            }
        )

        self.app_script.execute_function(AppsScriptFunction.RESOLVE_REQUEST, [self.current_level_id, "rejected"])

        self.pick_new_request()

    def on_later_pressed(self) -> None:
        requests.post(
            url=self.caretaker.api_root_url.removesuffix("/") + "/request/preapprove",
            json=dict(
                request_id=self.current_request_id
            ),
            headers={
                "x-key": self.caretaker.api_token
            }
        )

        self.app_script.execute_function(AppsScriptFunction.RESOLVE_REQUEST, [self.current_level_id, "later"])

        self.pick_new_request()

    def on_resend_form_link_pressed(self) -> None:
        self.youtube.post_message_to_live_chat(self.live_chat_id, self.caretaker.form_link)

    def on_clear_queue_pressed(self) -> None:
        self.app_script.execute_function(AppsScriptFunction.REOPEN_FORM)

    # TODO: Account for exceptions in all external service interactions, act accordingly (warn and ask for a manual action or require a restart)
    async def process_new_responses(self) -> None:
        rows = []
        for response in self.app_script.get_new_responses():
            if response.level_id in self.caretaker.last_stream_processed_levels:
                continue
            self.caretaker.last_stream_processed_levels.add(response.level_id)

            level = await get_level(response.level_id)
            if not level or level.grade != LevelGrade.UNRATED:
                continue

            rows.append([
                response.submission_timestamp.isoformat(),
                response.language.value,
                level.name,
                level.author_name,
                str(response.level_id),
                str(level.stars_requested),
                RequestedDifficulty.from_stars(level.stars_requested).value,
                response.showcase_link
            ])

        self.app_script.execute_function(AppsScriptFunction.APPEND_OPEN_REQUESTS, [rows])

        self.app_script.execute_function(AppsScriptFunction.CLEAR_NEW_RESPONSES)

        self.caretaker.save()

    def __init__(self) -> None:
        self.destroyed = False
        self.caretaker = Caretaker.load()

        self.video_link = ""  # Will be defined once the "Start Stream" btn is pressed
        self.live_chat_id = ""  # Will be defined once the "Start Stream" btn is pressed
        self.current_request_id = 0  # Will be defined once the first request is picked
        self.current_level_id = 0  # Will be defined once the first request is picked

        google_creds = get_credentials(token_path=Path('token.json'), client_secret_path="client_secret.json")
        self.app_script = AppsScriptApiWrapper(google_creds)
        self.youtube = YoutubeApiWrapper(google_creds)

        self.root = Tk()

        self.root.title('Request Bot Control Panel')
        self.root.geometry('800x600')

        self.tab_control = ttk.Notebook(self.root)

        self.stream_tab, self.options_tab, self.start_announcement_tab, self.end_goodbye_tab = build_tabs(self.tab_control, ['Stream', 'Options', 'Start Message', 'End Message'])

        self.start_stream_btn = ttk.Button(self.stream_tab, text="Start Stream", command=self.on_start_stream_pressed)
        self.start_stream_btn.place(relx=.5, rely=.5, anchor=CENTER)

        self.api_root_url_entry = build_option_row(self.options_tab, option_name='API Root URL', initial_value=self.caretaker.api_root_url)
        self.token_entry = build_option_row(self.options_tab, option_name='API Token', initial_value=self.caretaker.api_token, is_secret=True)
        self.channel_id_entry = build_option_row(self.options_tab, option_name='Channel ID', initial_value=self.caretaker.channel_id)
        self.form_link_entry = build_option_row(self.options_tab, option_name='Form Link', initial_value=self.caretaker.form_link)
        self.spreadsheet_link_entry = build_option_row(self.options_tab, option_name='Spreadsheet Link', initial_value=self.caretaker.spreadsheet_link)

        self.start_announcement_text_entry = ttk.Entry(self.start_announcement_tab)
        self.start_announcement_text_entry.insert(END, self.caretaker.start_announcement_text)
        self.start_announcement_text_entry.pack(side=LEFT, expand=False, fill='both')

        self.end_goodbye_text_entry = ttk.Entry(self.end_goodbye_tab)
        self.end_goodbye_text_entry.insert(END, self.caretaker.end_goodbye_text)
        self.end_goodbye_text_entry.pack(side=LEFT, expand=False, fill='both')

        self.streaming_mode_frame = ttk.Frame(self.stream_tab)

        self.end_stream_row = ttk.Frame(self.streaming_mode_frame)
        self.end_stream_button = ttk.Button(self.end_stream_row, text="End Stream", command=self.on_end_stream_pressed)
        self.end_stream_button.pack(LEFT)
        self.dump_remaining_requests_var = BooleanVar(value=True)
        self.dump_remaining_requests_checkbox = ttk.Checkbutton(self.end_stream_row, text="Dump remaining requests to bot", variable=self.dump_remaining_requests_var)
        self.dump_remaining_requests_checkbox.pack(LEFT)
        self.end_stream_row.pack(TOP, expand=True, fill='x')

        self.request_picking_options_row = ttk.Frame(self.streaming_mode_frame)
        self.is_random_var = BooleanVar(value=True)
        self.pick_randomly_radio_btn = ttk.Radiobutton(self.request_picking_options_row, text="Randomly", value=True, variable=self.is_random_var)
        self.pick_randomly_radio_btn.pack(LEFT)
        self.pick_sequentially_radio_btn = ttk.Radiobutton(self.request_picking_options_row, text="In Sequence", value=False, variable=self.is_random_var)
        self.pick_sequentially_radio_btn.pack(LEFT)
        self.alternate_var = BooleanVar(value=True)
        self.alternate_checkbox = ttk.Checkbutton(self.request_picking_options_row, text="Alternate", variable=self.alternate_var)
        self.alternate_checkbox.pack(LEFT)
        self.request_picking_options_row.pack(TOP, expand=True, fill='x')

        self.request_details_entry = ttk.Entry(self.streaming_mode_frame, state="readonly")
        self.request_details_entry.insert(END, "Pick a request to start")
        self.request_details_entry.pack(TOP, expand=True, fill='both')

        self.request_actions_row = ttk.Frame(self.streaming_mode_frame)
        self.pick_first_request_btn = ttk.Button(self.request_actions_row, text="Pick First Request", command=self.on_pick_first_request_pressed)
        self.pick_first_request_btn.pack(LEFT)
        self.approve_btn = ttk.Button(self.request_actions_row, text="Approve", command=self.on_approve_pressed)  # TODO: Replace with icon buttons (5 types)
        self.reject_btn = ttk.Button(self.request_actions_row, text="Reject", command=self.on_reject_pressed)  # TODO: Unify callback with approval buttons using functools.partial
        self.later_btn = ttk.Button(self.request_actions_row, text="Later", command=self.on_later_pressed)
        self.request_actions_row.pack(TOP, expand=True, fill='x')

        self.special_actions_row = ttk.Frame(self.streaming_mode_frame)
        self.resend_form_link_btn = ttk.Button(self.special_actions_row, text="Resend Form Link", command=self.on_resend_form_link_pressed)
        self.resend_form_link_btn.pack(LEFT)
        self.clear_queue_btn = ttk.Button(self.special_actions_row, text="Clear Queue", command=self.on_clear_queue_pressed)
        self.clear_queue_btn.pack(LEFT)
        self.special_actions_row.pack(TOP, expand=True, fill='x')

        self.tab_control.pack(expand=True, fill='both')

        sv_ttk.set_theme("light")

    async def run(self) -> None:
        self.tab_control.bind('<<NotebookTabChanged>>', self.on_tab_changed)
        self.root.bind('<Destroy>', self.on_exit)

        self.root.mainloop()


if __name__ == '__main__':
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    application = Application()

    try:
        loop.run_until_complete(application.run())
    except KeyboardInterrupt:
        pass
