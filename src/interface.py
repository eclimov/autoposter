from tkinter import messagebox
import tkinter as tk
import database
import autopost_v3 as autopost
import threading
import sys
from Project import Project
from file_control import resize_image
from PIL import ImageTk, Image


class Interface(tk.Tk):
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self, *args, **kwargs)
        self.wm_attributes("-topmost", 0)  # Set to 1 for topmost positioning
        self.resizable(False, False)
        self.title('Autoposter')
        self.configure(bg='white')

        self.project = Project()
        if not len(self.project.get_projects()):
            warning_label = tk.Label(self, text="No VK projects found in database", font="Arial 13")
            warning_label.pack()
            return

        self.toolbar = tk.Frame(self)
        self.toolbar.pack(side="top", fill="x", expand=False)

        self.project_var = tk.StringVar(self)
        self.project_var.set(self.project.get_name())  # default value
        self.project_var.trace("w", self.choose_project)
        projects_select = tk.OptionMenu(self.toolbar, self.project_var, *self.project.get_project_list())
        projects_select.pack(side="right")

        self.bottom_frame = tk.Frame(self)
        self.bottom_frame.pack(side="bottom", fill="x", expand=False)

        self.buttonbar = tk.Frame(self.bottom_frame)
        self.buttonbar.pack(side="right", expand=False)
        button_quit = tk.Button(
            self.buttonbar,
            bg="gray",
            text='Quit',
            font="Arial 14 bold",
            height=1,
            command=self.quit
        )
        button_quit.pack(side="right", padx=10, pady=10)
        self.button_post = tk.Button(
            self.buttonbar,
            bg="#88ce46",
            text='Post',
            font="Arial 14 bold",
            height=1,
            command=self.post
        )
        self.button_post.pack(side="right", pady=10)

        # TODO: allow choosing "signed" value
        '''
        self.signed_frame = tk.LabelFrame(self, text="Signed", bg="white")
        self.signed_frame.pack(side="bottom", anchor="w", padx="4", pady="4", expand=False)
        self.signed_var = tk.IntVar()
        signed_options = [
            ("Yes", "1"),
            ("No", "0"),
            ("Random", "-1")
        ]
        self.signed_var.set('1')
        for text, value in signed_options:
            b = tk.Radiobutton(self.signed_frame, text=text, font="Arial 7", bg="white", variable=self.signed_var, value=value)
            b.pack(anchor="w", pady=0, padx=4)
        '''

        self.status_info_label = tk.Label(
            self.buttonbar,
            text="",
            font="Arial 9",
            padx=10,
            anchor="w"
        )
        self.status_info_label.pack(side="right", pady=10)

        self.button_scheduled = tk.Button(self.toolbar, text="Scheduled", command=self.tab_scheduled)
        self.button_instant = tk.Button(self.toolbar, text="Instant", command=self.tab_instant)
        self.button_scheduled.pack(side="left")
        self.button_instant.pack(side="left")

        self.total_suggested = 0
        self.post_type = 1  # 1 - scheduled, 2- instant
        self.tab_scheduled()

    def project_init(self, project_name):
        self.project.set_project(project_name)

        self.status_info_label.config(text="Loading...", fg="black")

        def callback():
            self.button_post.config(state="disabled")
            self.button_scheduled.config(state="disabled")
            self.button_instant.config(state="disabled")

            if self.post_type == 1:  # Scheduled
                self.button_delete_all_planned.config(state="disabled")

            self.controller = autopost.Autopost(pname=self.project.get_name())

            if self.post_type == 1:  # Scheduled
                planned_posts = self.controller.get_auto_planned_posts()
                self.total_planned_posts = len(planned_posts)
                self.total_posts_label.config(text="Auto-planned posts: " + str(self.total_planned_posts))
                if self.total_planned_posts:
                    self.last_post.config(
                        text="Last planned post date: " + str(planned_posts[len(planned_posts)-1]['post_date'])
                    )
                else:
                    self.last_post.config(
                        text="Last planned post date: -"
                    )

                self.__avatar_path = self.controller.get_group_avatar()
                self.set_preview_image(self.__avatar_path)
            if self.post_type == 2:  # Instant
                self.post_difference = self.controller.get_post_difference()
                vk_post_count = int(self.post_difference['vk_post_count'])
                self.vk_checkbox.config(text="VK("+str(vk_post_count)+')')
                telegram_post_count = int(self.post_difference['telegram_post_count'])
                self.telegram_checkbox.config(text="Telegram(" + str(telegram_post_count) + ')')

                self.total_suggested = self.controller.get_posts(search_filter="suggests")['count']
                self.suggested_checkbox.config(
                    text="Post suggested("+str(self.total_suggested)+")",
                    state="normal" if self.total_suggested else "disabled"
                )

                for i in range(3):
                    value = tk.StringVar(self, value='' if i else '#' + self.project.get_name())
                    self.tags_forms[i + 1].config(textvariable=value)

            if self.post_type == 1:  # Scheduled
                self.button_delete_all_planned.config(state="normal")
            self.button_instant.config(state="normal")
            self.button_scheduled.config(state="normal")
            self.button_post.config(state="normal")
            self.status_info_label.config(text="", fg="black")
        t = threading.Thread(target=callback)
        t.start()

    def choose_project(self, name, index, mode):
        # print("callback called with name=%r, index=%r, mode=%r" % (name,index, mode))
        selected_value = self.getvar(name)
        self.project_init(selected_value)

    def confirm(self, text):
        delete = messagebox.askquestion("Confirm", text, icon='warning')
        if delete == 'yes':
            return True
        return False

    def set_preview_image(self, image_path='', grayscale=0):
        img = Image.open(image_path, 'r')
        if grayscale:
            img = img.convert(mode='LA')
        img = resize_image(img, 256, 256)
        tk_image = ImageTk.PhotoImage(img)
        self.panel.configure(image=tk_image)
        self.panel.image = tk_image

    def delete_all_planned(self):
        delete = False
        if self.total_planned_posts:
            delete = self.confirm(
                "You are going to delete "+str(self.total_planned_posts)+" planned posts. Are You Sure?"
            )
        if delete:
            def callback():
                self.button_post.config(state="disabled")
                self.button_delete_all_planned.config(state="disabled", text="Loading...")
                for delete_post in self.controller.delete_all_planned_posts():
                    if delete_post['status']:
                        self.total_planned_posts -= 1
                        self.total_posts_label.config(text="Auto-planned posts: " + str(self.total_planned_posts))
                        self.status_info_label.config(text=delete_post['message'], fg="#f49242")  # orange color
                    else:
                        self.status_info_label.config(text=delete_post['message'], fg="red")
                    if 'post_date' in delete_post:
                        self.last_post.config(text="Last planned post date: " + delete_post['post_date'])

                self.button_delete_all_planned.config(state="normal", text="Delete all")
                self.button_post.config(state="normal")

            t = threading.Thread(target=callback)
            t.start()

    def post(self):
        if self.post_type == 1:  # Scheduled
            days_number = self.number_of_days_scale.get()
            per_day = self.posts_per_day_scale.get()

            if days_number > 7 or per_day > 3:
                if not self.confirm("You are going to schedule "+str(days_number*per_day)+" posts\nnumber of days: "+str(days_number)+"\nper day: "+str(per_day)+"\nAre you sure?"):
                    return

            total_planned = days_number*per_day
            self.total_posted = 0

            def callback():
                self.button_delete_all_planned.config(state="disabled")
                self.button_post.config(state="disabled")
                # Maximum posts to be scheduled: 150
                for post in self.controller.add_posts(scheduled={'per_day': per_day, 'days_number': days_number}):
                    self.set_preview_image(post['image_path'])
                    self.last_post.config(text="Last planned post date: "+post['datetime_string'])
                    self.total_planned_posts += 1
                    self.total_posted += 1
                    if 'status' in post and post['status']:
                        status_text = "Scheduled: "+str(self.total_posted) + '/' + str(total_planned) + (" ✔" if self.total_posted==total_planned else '')
                        self.status_info_label.config(text=status_text, fg="green")
                    self.total_posts_label.config(text="Auto-planned posts: "+str(self.total_planned_posts))
                self.button_post.config(state="normal")
                self.button_delete_all_planned.config(state="normal")
            t = threading.Thread(target=callback)
            t.start()
        elif self.post_type == 2:  # Instant
            checkbox_vk = 1
            if not self.vk_var.get() or self.vk_checkbox['state'] == 'disabled':
                checkbox_vk = 0
            checkbox_auto_tags = 1
            if not self.tags_auto_var.get() or self.tags_auto_checkbox['state'] == 'disabled':
                checkbox_auto_tags = 0
            checkbox_telegram = 1
            if not self.telegram_var.get() or self.telegram_checkbox['state'] == 'disabled':
                checkbox_telegram = 0
            checkbox_telegram_link = 1
            if not self.telegram_vk_link_var.get() or self.telegram_vk_link_checkbox['state'] == 'disabled':
                checkbox_telegram_link = 0
            checkbox_auto_image = 1
            if not self.attachment_var.get() or self.attachment_checkbox['state'] == 'disabled':
                checkbox_auto_image = 0
            checkbox_suggested = 1
            if not self.suggested_var.get() or self.suggested_checkbox['state'] == 'disabled':
                checkbox_suggested = 0
            input_text = 1
            if self.text_input['state'] == 'disabled':
                input_text = 0

            vk_args = {'instant': {}}
            if checkbox_auto_image:
                vk_args['instant']['auto_image'] = 1
            text = ''
            if input_text:
                # 'get()' of 'Text' must have 'start' and 'end' arguments
                text = (self.text_input.get("1.0", 'end-1c')).strip()
            if text != '':
                vk_args['instant']['message'] = text
            if checkbox_auto_tags:
                vk_args['instant']['auto_tags'] = 1
            elif text != '' or checkbox_auto_image: # Do not post tags without attachment and/or text
                tags = ''
                for tag in self.tags_forms[1:]:
                    if tag['state'] != 'disabled' and (tag.get()).strip() != '' and '#' in str(tag.get()):
                        tags += ' ' + tag.get()
                    vk_args['instant']['vk_tags'] = tags.strip()
            if checkbox_suggested:
                vk_args['instant']['post_suggested'] = 1

            if checkbox_vk:
                vk_args['instant']['vk'] = 1

            if checkbox_telegram:
                vk_args['instant']['telegram'] = 1
                if checkbox_telegram_link:
                    vk_args['instant']['with_vk_link'] = 1

            def callback():
                self.button_post.config(state="disabled")
                for post in self.controller.add_posts(**vk_args):
                    if post:
                        if 'status' in post and post['status']:
                            if 'instant' in vk_args and 'post_suggested' in vk_args['instant']:
                                self.total_suggested -= 1
                                self.suggested_checkbox.config(text="Post suggested(" + str(self.total_suggested) + ")")
                            self.status_info_label.config(text="Posted ✔", fg="green")
                self.button_post.config(state="normal")
            t = threading.Thread(target=callback)
            t.start()

    def disable_checkboxes(self, name='', index='', mode=''):
        # print("callback called with name=%r, index=%r, mode=%r" % (name,index, mode))
        checkbox_vk = 1
        if not self.vk_var.get() or self.vk_checkbox['state'] == 'disabled':
            checkbox_vk = 0
        checkbox_auto_tags = 1
        if not self.tags_auto_var.get() or self.tags_auto_checkbox['state'] == 'disabled':
            checkbox_auto_tags = 0
        input_tags = 1

        checkbox_telegram = 1
        if not self.telegram_var.get() or self.telegram_checkbox['state'] == 'disabled':
            checkbox_telegram = 0
        checkbox_telegram_link = 1
        if not self.telegram_vk_link_var.get() or self.telegram_vk_link_checkbox['state'] == 'disabled':
            checkbox_telegram_link = 0

        checkbox_auto_image = 1
        if not self.attachment_var.get() or self.attachment_checkbox['state'] == 'disabled':
            checkbox_auto_image = 0
        checkbox_suggested = 1
        if not self.suggested_var.get() or self.suggested_checkbox['state'] == 'disabled':
            checkbox_suggested = 0
        input_text = 1

        checkbox_auto_tags_state = checkbox_vk and checkbox_auto_image
        input_tags_state = not checkbox_auto_tags and not checkbox_suggested
        checkbox_telegram_link_state = checkbox_telegram
        checkbox_auto_image_state = checkbox_vk and not checkbox_suggested
        checkbox_suggested_state = checkbox_vk and not checkbox_auto_image
        input_text_state = (checkbox_vk or checkbox_telegram) and not checkbox_suggested

        self.tags_auto_checkbox.config(state="normal" if checkbox_auto_tags_state else "disabled")
        for i in range(1, 4):
            self.tags_forms[i].config(state="normal" if input_tags_state else "disabled")
        self.telegram_vk_link_checkbox.config(state="normal" if checkbox_telegram_link_state else "disabled")
        self.attachment_checkbox.config(state="normal" if checkbox_auto_image_state else "disabled")
        self.suggested_checkbox.config(
            state="normal" if checkbox_suggested_state and self.total_suggested else "disabled"
        )
        self.text_input.config(
            state="normal" if input_text_state else "disabled", bg="white" if input_text_state else "#c1c1c1"
        )

    def tab_scheduled(self):
        try:
            self.forms_frame.destroy()
        except Exception as e:
            print('*' + str(e) + '*')
            pass
        self.post_type = 1
        self.forms_frame = tk.Frame(self, borderwidth=2, relief="groove")
        self.forms_frame.pack(side="top", fill="both", expand="True", padx=2, pady=2)
        forms = []
        frame_info = tk.LabelFrame(self.forms_frame, text="Planned", bg="white")
        forms.append(frame_info)
        forms[-1].grid(column=0, row=0, padx=4, pady=2, sticky="ew")

        self.button_delete_all_planned = tk.Button(
            frame_info,
            bg="#ff7777",
            text='Delete all',
            font="Arial 6",
            command=self.delete_all_planned
        )
        self.button_delete_all_planned.pack(side="right", padx=10, pady=10)

        self.total_posts_label = tk.Label(
            frame_info,
            bg="white",
            text="loading...",
            font="Arial 7", anchor="w"
        )
        self.total_posts_label.pack(side="top", fill="both", expand=True)

        self.last_post = tk.Label(
            frame_info,
            bg="white",
            text="loading...",
            font="Arial 7",
            anchor="w"
        )
        self.last_post.pack(side="top", fill="both", expand=True)

        frame_inputs = tk.LabelFrame(self.forms_frame)
        forms.append(frame_inputs)
        forms[-1].grid(column=0, row=1, padx=4, pady=2, sticky="ew")
        # TODO: set 'to' value dependent of total planned posts
        self.number_of_days_scale = tk.Scale(
            frame_inputs,
            from_=0, to=7, orient=tk.HORIZONTAL, tickinterval=1, label="Number of days"
        )
        self.number_of_days_scale.pack(fill="both", expand=True)
        self.number_of_days_scale.set(3)
        self.posts_per_day_scale = tk.Scale(
            frame_inputs,
            from_=0, to=10,
            orient=tk.HORIZONTAL, tickinterval=2, label="Per day"
        )
        self.posts_per_day_scale.pack(fill="both", expand=True)
        self.posts_per_day_scale.set(2)

        image_viewer = tk.LabelFrame(self.forms_frame)
        forms.append(image_viewer)
        forms[-1].grid(column=0, row=2, padx=4, pady=2, sticky="ew")
        self.panel = tk.Label(image_viewer, width=256, height=256)
        self.set_preview_image(image_path="assets/autoposter_avatar_big.jpg",grayscale=1)
        self.panel.pack(side="bottom", fill="both", expand="yes")

        self.forms_frame.grid_columnconfigure(0, weight=1)

        self.project_init(self.project.get_name())

    def tab_instant(self):
        try:
            self.forms_frame.destroy()
        except Exception as e:
            print('*' + str(e) + '*')
            pass
        self.post_type = 2
        self.forms_frame = tk.Frame(self, borderwidth=2, relief="groove")
        self.forms_frame.pack(side="top", fill="both", expand="True", padx=2, pady=2)
        forms = []

        ################################################################################
        self.vk_frame = tk.LabelFrame(self.forms_frame, bg="#466991")
        forms.append(self.vk_frame)
        self.vk_var = tk.IntVar()
        self.vk_var.set(1)
        self.vk_checkbox = tk.Checkbutton(self.vk_frame, variable=self.vk_var, text="VK", font="Arial 13")
        self.vk_var.trace("w", self.disable_checkboxes)
        self.vk_checkbox.grid(column=0, row=0, padx=4, pady=2, sticky="ew")

        forms[-1].grid(column=0, row=0, padx=4, pady=2, sticky="ew")

        self.tags_frame = tk.Frame(self.vk_frame, borderwidth=1, relief="groove")
        self.tags_forms = []
        self.tags_auto_var = tk.IntVar()
        self.tags_auto_var.set(0)
        self.tags_auto_checkbox = tk.Checkbutton(
            self.tags_frame,
            variable=self.tags_auto_var, text="Auto-tags", font="Arial 6"
        )
        self.tags_auto_var.trace("w", self.disable_checkboxes)
        self.tags_forms.append(self.tags_auto_checkbox)
        self.tags_forms[0].grid(column=0, row=0, padx=2, pady=2, sticky="ew")
        for i in range(3):
            value = tk.StringVar(self, value='' if i else '#'+self.project.get_name())
            tag_input = tk.Entry(self.tags_frame, width="7", textvariable=value)
            self.tags_forms.append(tag_input)
            self.tags_forms[i+1].grid(column=i+1, row=0, padx=4, pady=2, sticky="ew")
        forms.append(self.tags_frame)

        forms[-1].grid(column=0, row=1, padx=4, pady=2, sticky="ew")
        ################################################################################

        ################################################################################
        self.telegram_frame = tk.LabelFrame(self.forms_frame, bg="#37aee2")
        forms.append(self.telegram_frame)
        self.telegram_var = tk.IntVar()
        self.telegram_var.set(1)
        self.telegram_checkbox = tk.Checkbutton(
            self.telegram_frame,
            variable=self.telegram_var,
            text="Telegram",
            font="Arial 13",
            width="12",
            anchor="w"
        )
        self.telegram_var.trace("w", self.disable_checkboxes)
        self.telegram_checkbox.grid(column=0, row=0, padx=4, pady=2, sticky="nw")

        self.telegram_vk_link_var = tk.IntVar()
        self.telegram_vk_link_var.set(0)
        self.telegram_vk_link_checkbox = tk.Checkbutton(
            self.telegram_frame,
            variable=self.telegram_vk_link_var,
            text="With VK link",
            font="Arial 11",
            width="12",
            anchor="w"
        )
        self.telegram_vk_link_checkbox.grid(column=0, row=1, padx=4, pady=2, sticky="nw")

        forms[-1].grid(column=1, row=0, padx=4, pady=2, sticky="n")
        ################################################################################

        ################################################################################
        self.attachment_frame = tk.LabelFrame(self.forms_frame, bg="#f4d142")
        forms.append(self.attachment_frame)
        self.attachment_var = tk.IntVar()
        self.attachment_var.set(0)
        self.attachment_checkbox = tk.Checkbutton(
            self.attachment_frame,
            variable=self.attachment_var,
            text="Attach image(auto-choose)",
            font="Arial 7"
        )
        self.attachment_var.trace("w", self.disable_checkboxes)
        self.attachment_checkbox.pack(fill="both", padx="3", pady="3")
        #self.attachment_checkbox.grid(column=0, row=1, padx=4, pady=2, sticky="e")
        forms[-1].grid(column=0, row=2, padx=4, pady=2, sticky="ew", columnspan="2")
        ################################################################################

        ################################################################################
        self.suggested_frame = tk.LabelFrame(self.forms_frame, bg="#502693")
        forms.append(self.suggested_frame)
        self.suggested_var = tk.IntVar()
        self.suggested_var.set(0)
        self.suggested_checkbox = tk.Checkbutton(
            self.suggested_frame,
            variable=self.suggested_var,
            text="loading...",
            font="Arial 7",
            state="disabled"
        )
        self.suggested_var.trace("w", self.disable_checkboxes)
        self.suggested_checkbox.pack(fill="both", padx="3", pady="3")
        #self.attachment_checkbox.grid(column=0, row=1, padx=4, pady=2, sticky="e")
        forms[-1].grid(column=0, row=3, padx=4, pady=2, sticky="ew", columnspan="2")
        ################################################################################

        ################################################################################
        self.text_input = tk.Text(self.forms_frame, width="21", height="4")
        forms.append(self.text_input)
        forms[-1].grid(column=0, row=4, padx=4, pady=2, sticky="ew", columnspan="2")
        ################################################################################

        self.project_init(self.project.get_name())
        self.disable_checkboxes()

    def quit(self):
        sys.exit()
