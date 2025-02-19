from pathlib import Path
from tkinter import messagebox, Tk, ttk
from tkinter.constants import CENTER, END, LEFT, TOP

import jinja2

from apps_script import AppsScriptApiWrapper, AppsScriptFunction
from component_builder import build_option_row, build_tabs
from gd import get_level, RequestedDifficulty
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

        live_chat_id = self.youtube.get_live_chat_id(video_id)
        self.youtube.post_message_to_live_chat(live_chat_id, self.caretaker.form_link)

    def shift_to_stream_layout(self) -> None:
        self.start_stream_btn.pack_forget()

        # TODO: Arrange streaming mode components

    def on_start_stream_pressed(self) -> None:
        video_id = self.youtube.get_live_stream_video_id(self.caretaker.channel_id)

        if video_id:
            self.video_link = f"https://www.youtube.com/watch?v={video_id}"
            if video_id != self.caretaker.last_stream_id:
                self.perform_stream_startup_routine(video_id)
                self.caretaker.last_stream_id = video_id
                self.caretaker.save()
            self.shift_to_stream_layout()
        else:
            messagebox.showerror(None, "Not found")

    # TODO: Account for exceptions in all external service interactions, act accordingly (warn and ask for a manual action or require a restart)
    async def process_new_responses(self) -> None:
        rows = []
        for response in self.app_script.get_new_responses():
            level = await get_level(response.level_id)
            if not level:
                continue

            # TODO: Perform all sorts of checks on this level (incl. duplicates during the stream - store ID set somewhere)

            rows.append([
                response.submission_timestamp.isoformat(),
                response.language.value,
                level.name,
                level.author_name,
                str(response.level_id),
                str(response.stars),  # TODO: Get stars from API, delete the corresponding questions from the form, adapt the spreadsheet, connection and retrieval function
                RequestedDifficulty.from_stars(response.stars).value,
                response.showcase_link
            ])

        self.app_script.execute_function(AppsScriptFunction.APPEND_OPEN_REQUESTS, [rows])

        self.app_script.execute_function(AppsScriptFunction.CLEAR_NEW_RESPONSES)

    def __init__(self) -> None:
        self.destroyed = False
        self.caretaker = Caretaker.load()

        self.video_link = ""  # Will be defined once the "Start Stream" btn is pressed

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

        # TODO: Initialize (but not pack) streaming mode components

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
