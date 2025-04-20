import kivy
from kivy.app import App
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.gridlayout import GridLayout
from kivy.clock import Clock
import datetime
from kivy.uix.popup import Popup
from kivy.uix.textinput import TextInput
from kivy.graphics import Color, Rectangle
from kivy.uix.scrollview import ScrollView
from kivy.uix.screenmanager import ScreenManager, Screen, NoTransition

# Import necessary modules for data persistence
import json
import os
import sys


# importar Plyer
try:
    from plyer import calendar
    PLYER_CALENDAR_AVAILABLE = True
    print("[INFO ] Plyer Calendar module imported successfully.")
except ImportError:
    PLYER_CALENDAR_AVAILABLE = False
    print("[WARNING] Plyer Calendar module not available. Install plyer (`pip install plyer`) for calendar integration.")
except NotImplementedError:
    PLYER_CALENDAR_AVAILABLE = False
    print("[WARNING] Plyer Calendar backend not implemented for this platform.")


# Opcional: Especifique a versão mínima necessária do Kivy
kivy.require('2.0.0')


class DateTimeEncoder(json.JSONEncoder):
    """Converte objetos datetime para strings ISO 8601 ao serializar para JSON."""
    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            return obj.isoformat()
        return super().default(obj) # Let the base class default method raise the TypeError for other types

def datetime_decoder(json_object):
    """Converte strings ISO 8601 de volta para objetos datetime ao deserializar de JSON."""
    for key, value in json_object.items():
        if isinstance(value, str):
            try:
                # Tenta parsear a string como datetime ISO 8601
                json_object[key] = datetime.datetime.fromisoformat(value)
            except ValueError:
                # Se falhar, mantém o valor como estava (pode não ser uma string de data)
                pass
    return json_object


# --- Definição da Tela de Alerta ---
class AlertScreen(Screen):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        alert_layout = BoxLayout(orientation='vertical', spacing=20, padding=30)

        self.alert_message_label = Label(text='Mensagem de Alerta Aqui',
                                          font_size=25, halign='center', valign='middle',
                                          text_size=(self.width * 0.8, None))

        dismiss_button = Button(text='Entendido',
                                font_size=20,
                                size_hint=(None, None),
                                size=(200, 70),
                                pos_hint={'center_x': 0.5})


        dismiss_button.bind(on_press=self.dismiss_alert)

        alert_layout.add_widget(self.alert_message_label)
        alert_layout.add_widget(dismiss_button)

        self.add_widget(alert_layout)

        self.bind(size=self._update_label_text_size)

    def _update_label_text_size(self, instance, value):
         self.alert_message_label.text_size = (self.width * 0.8, None)


    def dismiss_alert(self, instance):
        self.manager.current = 'main_screen'


# --- Definição da Segunda Tela (Vencidos) ---
class ExpiredScreen(Screen):
    expired_clients_list_layout = None
    expired_clients_box_layout = None


    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        expired_main_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)

        expired_main_layout.add_widget(Label(text='Clientes Vencidos',
                                       font_size=30, size_hint_y=None, height=50,
                                       halign='center', valign='middle'))


        self.expired_clients_box_layout = BoxLayout(orientation='vertical',
                                                    padding=10, spacing=5,
                                                    size_hint_y=1)

        with self.expired_clients_box_layout.canvas.before:
            Color(1, 0, 0, 1) # Cor vermelha
            self.red_list_rect = Rectangle(pos=self.expired_clients_box_layout.pos,
                                           size=self.expired_clients_box_layout.size)

        self.expired_clients_box_layout.bind(pos=self.update_red_list_rect, size=self.update_red_list_rect)


        expired_list_scrollview = ScrollView(size_hint=(1, 1))

        self.expired_clients_list_layout = BoxLayout(orientation='vertical', spacing=5, size_hint_y=None)
        self.expired_clients_list_layout.bind(minimum_height=self.expired_clients_list_layout.setter('height'))

        expired_list_scrollview.add_widget(self.expired_clients_list_layout)

        self.expired_clients_box_layout.add_widget(expired_list_scrollview)

        expired_main_layout.add_widget(self.expired_clients_box_layout)


        back_button = Button(text='Voltar',
                             font_size=20,
                             size_hint=(None, None),
                             size=(150, 60),
                             pos_hint={'center_x': 0.5})

        back_button.bind(on_press=self.go_back_to_main)
        expired_main_layout.add_widget(back_button)

        self.add_widget(expired_main_layout)

    def update_red_list_rect(self, instance, value):
        self.red_list_rect.pos = instance.pos
        self.red_list_rect.size = instance.size


    def go_back_to_main(self, instance):
        self.manager.current = 'main_screen'


# --- Definição da Aplicação Principal ---
class MobileApp(App):
    clients_list = [] # Lista de clientes ATIVOS
    expired_clients_list = [] # Lista de clientes VENCIDOS
    total_timer_duration = datetime.timedelta(hours=23, minutes=55)
    active_timer_labels = [] # Lista para manter referências aos rótulos de timer ativos


    def build(self):
        self.sm = ScreenManager(transition=NoTransition())

        # >>>>> Configura o caminho do arquivo de dados <<<<<
        self.save_file_path = os.path.join(self.user_data_dir, 'client_data.json')
        print(f"[INFO ] User data directory: {self.user_data_dir}")
        print(f"[INFO ] Save file path: {self.save_file_path}")

        self.load_data()

        # --- Cria a Tela Principal (contém a lista ATIVA) ---
        main_screen = Screen(name='main_screen')
        main_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)

        # Hora Principal
        self.time_label = Label(text='Carregando...',
                                font_size=48,
                                halign='center',
                                valign='middle',
                                size_hint_y=0.1)


        self.all_clients_box_layout = BoxLayout(orientation='vertical',
                                                size_hint_y=0.55,
                                                padding=10, spacing=5)

        with self.all_clients_box_layout.canvas.before:
            Color(0.8, 0.8, 0.8, 1)
            self.all_clients_rect = Rectangle(pos=self.all_clients_box_layout.pos,
                                              size=self.all_clients_box_layout.size)
        self.all_clients_box_layout.bind(pos=self.update_all_rect, size=self.update_all_rect)

        self.client_list_scrollview = ScrollView(size_hint=(1, 1))
        self.client_list_layout = BoxLayout(orientation='vertical', spacing=5, size_hint_y=None)
        self.client_list_layout.bind(minimum_height=self.client_list_layout.setter('height'))

        self.client_list_scrollview.add_widget(self.client_list_layout)
        self.all_clients_box_layout.add_widget(self.client_list_scrollview)


        self.info_label = Label(text='Use o botão abaixo para adicionar clientes',
                                 font_size=20,
                                 halign='center',
                                 valign='middle',
                                 size_hint_y=0.1)

        main_buttons_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=60)


        open_add_client_button = Button(text='Adicionar Novo Cliente', font_size=20)
        open_add_client_button.bind(on_press=self.show_add_client_popup)

        expired_clients_button = Button(text='Vencidos', font_size=20)
        expired_clients_button.bind(on_press=self.go_to_expired_screen)



        main_layout.add_widget(self.time_label)
        main_layout.add_widget(self.all_clients_box_layout) # Caixa cinza com a lista ATIVA
        main_layout.add_widget(self.info_label)
        main_layout.add_widget(main_buttons_layout)

        main_screen.add_widget(main_layout)

        #  Segunda Tela (Vencidos - contem a lista VENCIDA) ---
        expired_screen = ExpiredScreen(name='expired_screen')

        # --- Cria a Tela de Alerta ---
        alert_screen = AlertScreen(name='alert_screen')


        # --- Adiciona as telas ao ScreenManager ---
        self.sm.add_widget(main_screen)
        self.sm.add_widget(expired_screen)
        self.sm.add_widget(alert_screen)


        # --- Inicialização e Agendamento ---
        self.update_time()
        Clock.schedule_interval(self.update_time, 1)

        # Atualiza as exibições APÓS carregar os dados <<<<<
        self.update_client_list_display()
        self.update_expired_list_display()

        # O timer está agendado para rodar a cada segundo.
        Clock.schedule_interval(self.update_timers, 1)


        return self.sm


    # >>>>> Método para salvar os dados <<<<<
    def save_data(self):
        """Salva as listas de clientes ativos e vencidos em um arquivo JSON."""
        data_to_save = {
            'active': self.clients_list,
            'expired': self.expired_clients_list
        }
        try:
            os.makedirs(self.user_data_dir, exist_ok=True)
            with open(self.save_file_path, 'w') as f:
                json.dump(data_to_save, f, indent=4, cls=DateTimeEncoder)
            print(f"[INFO ] Data saved successfully to {self.save_file_path}")
        except Exception as e:
            print(f"[ERROR] Failed to save data: {e}")


    # >>>>> Método para carregar os dados <<<<<
    def load_data(self):
        """Carrega as listas de clientes ativos e vencidos de um arquivo JSON."""
        self.clients_list = [] # Inicia com listas vazias
        self.expired_clients_list = []
        if os.path.exists(self.save_file_path):
            try:
                with open(self.save_file_path, 'r') as f:
                    # Usa o object_hook para deserializar datetime strings
                    loaded_data = json.load(f, object_hook=datetime_decoder)

                if 'active' in loaded_data and isinstance(loaded_data['active'], list):
                    self.clients_list = loaded_data['active']
                    # Garante flags para clientes antigos que não tinham status/calendar_event_created
                    for client in self.clients_list:
                         if 'calendar_event_created' not in client:
                              client['calendar_event_created'] = False
                         if 'status' not in client: # Garante status para clientes antigos
                              client['status'] = 'active'


                if 'expired' in loaded_data and isinstance(loaded_data['expired'], list):
                    self.expired_clients_list = loaded_data['expired']
                    # Garante flags para clientes antigos em expirados
                    for client in self.expired_clients_list:
                         if 'calendar_event_created' not in client:
                              client['calendar_event_created'] = False
                         if 'status' not in client:
                             # Tenta deduzir o status para clientes antigos sem o campo
                             if client.get('creation_time') is not None and isinstance(client.get('creation_time'), datetime.datetime):
                                  # Se tem creation_time e é um datetime, tenta ver se já passou do timer total
                                  try:
                                       if datetime.datetime.now() - client['creation_time'] > self.total_timer_duration:
                                            client['status'] = 'expired'
                                       else: # Se creation_time existe mas não expirou (o que não deveria acontecer em 'expired_clients_list'), assume manual
                                            client['status'] = 'deleted_manual'
                                  except TypeError: # Catch error if creation_time is not a datetime object for some reason
                                       client['status'] = 'deleted_manual'
                             else: # Se não tem creation_time, assume que foi deletado manualmente (pode não ser preciso)
                                  client['status'] = 'deleted_manual'


                print(f"[INFO ] Data loaded successfully from {self.save_file_path}")
            except json.JSONDecodeError as e:
                 print(f"[ERROR] Failed to decode JSON from {self.save_file_path}: {e}")
                 print("[ERROR] Data file might be corrupted. Starting with empty lists.")
                 self.clients_list = []
                 self.expired_clients_list = []
            except Exception as e:
                 print(f"[ERROR] Failed to load data from {self.save_file_path}: {e}")
                 print("[ERROR] Starting with empty lists.")
                 self.clients_list = []
                 self.expired_clients_list = []
        else:
            print(f"[INFO ] Save file not found at {self.save_file_path}. Starting with empty lists.")


    # método on_stop para salvar os dados ao fechar 
    def on_stop(self):
        """Salva os dados dos clientes quando o aplicativo é fechado."""
        print("[INFO ] App stopping. Saving data...")
        self.save_data()


    def update_status_rect(self, instance, value):
        """Atualiza a posição e tamanho do retângulo de fundo do rótulo de status."""
        if hasattr(instance, 'status_bg_rect'):
             instance.status_bg_rect.pos = instance.pos
             instance.status_bg_rect.size = instance.size


    #popup de confirmação de exclusão (da lista ATIVA)
    def show_delete_confirmation_popup(self, instance):
        """Exibe um popup pedindo confirmação para excluir um cliente da lista ativa."""
        client_to_confirm = instance.client_data

        popup_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)

        popup_message = Label(text=f"Tem certeza que deseja excluir\n{client_to_confirm.get('nome', 'este cliente')}?",
                              font_size=20, halign='center', valign='middle',
                              text_size=(self.sm.width * 0.7, None))


        button_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=50)

        yes_button = Button(text='Sim', font_size=20)
        # Este botão "Sim" chama o método que MOVE para a lista de vencidos
        yes_button.bind(on_press=lambda btn: self.confirm_delete(client_to_confirm, confirmation_popup))

        no_button = Button(text='Não', font_size=20)
        no_button.bind(on_press=lambda btn: confirmation_popup.dismiss())

        button_layout.add_widget(yes_button)
        button_layout.add_widget(no_button)

        popup_layout.add_widget(popup_message)
        popup_layout.add_widget(button_layout)

        confirmation_popup = Popup(title='Confirmar Exclusão',
                                   content=popup_layout,
                                   size_hint=(0.8, 0.4),
                                   auto_dismiss=False)

        confirmation_popup.open()

    # popup de confirmação de exclusão (da lista VENCIDA) <<<<<
    def show_expired_delete_confirmation_popup(self, instance):
        """Exibe um popup pedindo confirmação para excluir PERMANENTEMENTE um cliente da lista vencida."""
        client_to_confirm = instance.client_data

        popup_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)

        popup_message = Label(text=f"Tem certeza que deseja excluir\nPERMANENTEMENTE {client_to_confirm.get('nome', 'este cliente')}?",
                              font_size=20, halign='center', valign='middle',
                              text_size=(self.sm.width * 0.7, None))


        button_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=50)

        yes_button = Button(text='Sim', font_size=20)
        # Este botão "Sim" chama o método que REMOVE da lista de vencidos
        yes_button.bind(on_press=lambda btn: self.confirm_expired_delete(client_to_confirm, expired_confirmation_popup))

        no_button = Button(text='Não', font_size=20)
        no_button.bind(on_press=lambda btn: expired_confirmation_popup.dismiss())

        button_layout.add_widget(yes_button)
        button_layout.add_widget(no_button)

        popup_layout.add_widget(popup_message)
        popup_layout.add_widget(button_layout)

        expired_confirmation_popup = Popup(title='Confirmar Exclusão Permanente',
                                           content=popup_layout,
                                           size_hint=(0.8, 0.4),
                                           auto_dismiss=False)

        expired_confirmation_popup.open()


    # Modificado: Transfere o cliente para a lista de vencidos com status "excluído manualmente"
    def confirm_delete(self, client_to_delete, popup_instance):
        """Move o cliente da lista ativa para a lista de vencidos com status 'deleted_manual'."""
        if client_to_delete in self.clients_list:
            client_to_delete['status'] = 'deleted_manual'

            self.clients_list.remove(client_to_delete)
            self.expired_clients_list.append(client_to_delete)

            print(f"\nCliente excluído manualmente (movido para vencidos): {client_to_delete.get('nome', 'Desconhecido')} ({client_to_delete.get('mac', 'Desconhecido')})\n")
            self.info_label.text = f"Cliente {client_to_delete.get('nome', 'Desconhecido')} excluído e movido para vencidos."

            self.update_client_list_display()
            self.update_expired_list_display()

            popup_instance.dismiss()

        else:
            print("Erro: Cliente não encontrado na lista ativa para exclusão manual.")
            self.info_label.text = "Erro ao excluir cliente."
            popup_instance.dismiss()

    # excluir PERMANENTEMENTE da lista VENCIDA 
    def confirm_expired_delete(self, client_to_delete, popup_instance):
        """Remove o cliente permanentemente da lista de vencidos."""
        if client_to_delete in self.expired_clients_list:
            self.expired_clients_list.remove(client_to_delete)

            print(f"\nCliente excluído permanentemente: {client_to_delete.get('nome', 'Desconhecido')} ({client_to_delete.get('mac', 'Desconhecido')})\n")
            self.info_label.text = f"Cliente {client_to_delete.get('nome', 'Desconhecido')} excluído permanentemente."

            self.update_expired_list_display() # Atualiza APENAS a exibição da lista de vencidos

            popup_instance.dismiss()

        else:
            print("Erro: Cliente não encontrado na lista vencida para exclusão permanente.")
            self.info_label.text = "Erro ao excluir cliente permanentemente."
            popup_instance.dismiss()


    def show_alert_screen(self, message):
        """Muda para a tela de alerta e define a mensagem."""
        alert_screen_instance = self.sm.get_screen('alert_screen')
        alert_screen_instance.alert_message_label.text = message
        self.sm.current = 'alert_screen'


    def go_to_expired_screen(self, instance):
        """Muda a tela atual do ScreenManager para a tela de Clientes Vencidos."""
        self.update_expired_list_display()
        self.sm.current = 'expired_screen'

    def update_all_rect(self, instance, value):
        """Atualiza a posição e o tamanho do retângulo de fundo da caixa cinza principal."""
        self.all_clients_rect.pos = instance.pos
        self.all_clients_rect.size = instance.size

    def update_time(self, *args):
        """Atualiza o texto do time_label com a hora atual."""
        now = datetime.datetime.now()
        time_str = now.strftime('%H:%M:%S')
        self.time_label.text = time_str

    def update_client_list_display(self):
        """Limpa a lista de exibição e a preenche com os clientes ATIVOS atuais."""
        self.client_list_layout.clear_widgets()
        self.active_timer_labels.clear() # Limpa a lista de rótulos de timer ao redesenhar


        if not self.clients_list:
            self.client_list_layout.add_widget(Label(text='Nenhum cliente ATIVO cadastrado.',
                                                      halign='center', valign='middle', size_hint_y=None, height=100, color=(0,0,0,1)))
            return

        list_layout_width = self.client_list_layout.width if self.client_list_layout.width > 10 else 400


        for index, client in enumerate(self.clients_list):
            # Altura da linha para acomodar o texto verticalmente
            client_row_layout = BoxLayout(orientation='horizontal', spacing=5, padding=5, size_hint_y=None, height=100)


            num_label = Label(text=f"{index + 1}.", font_size=18, size_hint_x=0.1, halign='right', valign='middle', color=(0,0,0,1),
                              size_hint_y=1)


            details_layout = BoxLayout(orientation='vertical', spacing=2, size_hint_x=0.5,
                                       size_hint_y=None)


            nome_label = Label(text=f"Nome: {client.get('nome', 'N/A')}",
                               font_size=15, halign='left', valign='top', color=(0,0,0,1),
                               text_size=((list_layout_width * 0.5 * 0.95), None), size_hint_y=None)

            mac_label = Label(text=f"MAC: {client.get('mac', 'N/A')}",
                              font_size=15, halign='left', valign='middle', color=(0,0,0,1),
                              text_size=((list_layout_width * 0.5 * 0.95), None), size_hint_y=None)

            senha_status_label = Label(text=f"Senha: {client.get('senha', 'N/A')}",
                                       font_size=15, halign='left', valign='bottom', color=(0,0,0,1),
                                       text_size=((list_layout_width * 0.5 * 0.95), None), size_hint_y=None)


            details_layout.add_widget(nome_label)
            details_layout.add_widget(mac_label)
            details_layout.add_widget(senha_status_label)


            timer_label = Label(text="Timer: --:--:--", font_size=16, size_hint_x=0.3, halign='center', valign='middle', color=(0,0,0,1),
                                size_hint_y=1)
            timer_label.client_creation_time = client.get('creation_time')
            timer_label.is_timer_label = True


            delete_button = Button(text='X',
                                   font_size=18,
                                   size_hint_x=0.1,
                                   size_hint_y=1,
                                   background_color=(1, 0, 0, 1))

            delete_button.client_data = client
            # Este botão chama o popup que MOVE para a lista de vencidos
            delete_button.bind(on_press=self.show_delete_confirmation_popup)


            # Adiciona o rótulo do timer à lista de rótulos ativos
            self.active_timer_labels.append(timer_label)


            client_row_layout.add_widget(num_label)
            client_row_layout.add_widget(details_layout)
            client_row_layout.add_widget(timer_label)
            client_row_layout.add_widget(delete_button)


            self.client_list_layout.add_widget(client_row_layout)


    def update_expired_list_display(self):
        """Limpa a lista de exibição de vencidos e a preenche com os clientes vencidos em layout horizontal, incluindo botão de exclusão."""
        expired_screen = self.sm.get_screen('expired_screen')
        expired_layout = expired_screen.expired_clients_list_layout

        expired_layout.clear_widgets()

        if not self.expired_clients_list:
             expired_layout.add_widget(Label(text='Nenhum cliente VENCIDO ou EXCLUÍDO ainda.',
                                             halign='center', valign='middle', size_hint_y=None, height=100, color=(0,0,0,1)))
             return

        expired_list_container_width = expired_screen.expired_clients_box_layout.width if expired_screen.expired_clients_box_layout.width > 10 else 400

        # Altura ajustada para a linha horizontal de vencidos/excluídos
        row_height = 40 # Pode precisar de ajuste conforme necessário para caber o texto

        # >>>>> NOVO: Proporções ajustadas para incluir o botão de exclusão (total 1.0) <<<<<
        # Exemplo de proporções: Num (0.1) | Nome (0.18) | MAC (0.18) | Senha (0.18) | Status (0.26) | Delete (0.1) = 1.0
        num_width_hint = 0.1
        detail_width_hint = 0.18
        status_width_hint = 0.26
        delete_width_hint = 0.1

        base_text_width = expired_list_container_width

        for index, client in enumerate(self.expired_clients_list):
            # Layout HORIZONTAL para cada linha de cliente VENCIDO/EXCLUÍDO
            expired_row_layout = BoxLayout(orientation='horizontal', spacing=5, padding=5, size_hint_y=None, height=row_height)


            num_label = Label(text=f"{index + 1}.", font_size=15, size_hint_x=num_width_hint, halign='right', valign='middle', color=(0,0,0,1))

            # Labels para os dados do cliente (Nome, MAC, Senha Status)
            nome_label = Label(text=f"Nome: {client.get('nome', 'N/A')}",
                               font_size=14, size_hint_x=detail_width_hint, halign='left', valign='middle', color=(0,0,0,1),
                               text_size=((base_text_width * detail_width_hint * 0.95), None))

            mac_label = Label(text=f"MAC: {client.get('mac', 'N/A')}",
                              font_size=14, size_hint_x=detail_width_hint, halign='left', valign='middle', color=(0,0,0,1),
                              text_size=((base_text_width * detail_width_hint * 0.95), None))

            senha_status_label = Label(text=f"Senha: {client.get('senha', 'N/A')}",
                                       font_size=14, size_hint_x=detail_width_hint, halign='left', valign='middle', color=(0,0,0,1),
                                       text_size=((base_text_width * detail_width_hint * 0.95), None))


            # Rótulo para exibir o STATUS (VENCIDO ou EXCLUÍDO MANUALMENTE)
            status_label = Label(font_size=16, size_hint_x=status_width_hint, halign='center', valign='middle',
                                 markup=True)

            client_status = client.get('status', 'expired')

            status_text = ""
            status_color = (0,0,0,1)


            if client_status == 'expired':
                status_text = "VENCIDO"
                status_color = (1, 0, 0, 1)
                with status_label.canvas.before:
                    Color(1, 0, 0, 1)
                    status_label.status_bg_rect = Rectangle(pos=status_label.pos, size=status_label.size)
                status_label.bind(pos=self.update_status_rect, size=self.update_status_rect)
                status_label.color = (1, 1, 1, 1)


            elif client_status == 'deleted_manual':
                status_text = "EXCLUÍDO"
                status_color = (0, 0, 1, 1)
                with status_label.canvas.before:
                    Color(0.7, 0.7, 0.7, 1) # Fundo cinza claro
                    status_label.status_bg_rect = Rectangle(pos=status_label.pos, size=status_label.size)
                status_label.bind(pos=self.update_status_rect, size=self.update_status_rect)
                status_label.color = (0, 0, 0, 1)


            status_label.text = f"[b]{status_text}[/b]"
            status_label.text_size = ((base_text_width * status_width_hint * 0.95), None)

            expired_delete_button = Button(text='X',
                                           font_size=18,
                                           size_hint_x=delete_width_hint,
                                           size_hint_y=1,
                                           background_color=(1, 0, 0, 1))

            expired_delete_button.client_data = client
            expired_delete_button.bind(on_press=self.show_expired_delete_confirmation_popup)


            expired_row_layout.add_widget(num_label)
            expired_row_layout.add_widget(nome_label)
            expired_row_layout.add_widget(mac_label)
            expired_row_layout.add_widget(senha_status_label)
            expired_row_layout.add_widget(status_label)
            expired_row_layout.add_widget(expired_delete_button) # Adiciona o botão de exclusão no final


            expired_layout.add_widget(expired_row_layout)


    def update_timers(self, dt):
        """Calcula e atualiza o tempo restante para clientes ATIVOS e move expirados."""
        now = datetime.datetime.now()
        expired_clients_this_tick = [] # Lista para clientes que expiram NESTA tick

        #Identificar clientes que expiraram nesta tick (Itera sobre a lista de DADOS ativos) ---
        for client_data in list(self.clients_list): # Usa uma cópia
            creation_time = client_data.get('creation_time')
            if creation_time is None:
                continue

            elapsed_time = now - creation_time
            time_remaining = self.total_timer_duration - elapsed_time

            if time_remaining.total_seconds() <= 0 and not client_data.get('calendar_event_created', False):
                 expired_clients_this_tick.append(client_data)
                 client_data['status'] = 'expired'


                 # --- Lógica de Criação de Lembrete (TENTATIVA VIA PLYER) ---
                 client_name = client_data.get('nome', 'Desconhecido')
                 client_mac = client_data.get('mac', 'Desconhecido')
                 event_time = now
                 event_title = f"Cliente Expirado: {client_name}"
                 event_description = f"MAC: {client_mac}\nStatus Senha: [Salva]\nCriado em: {creation_time.strftime('%Y-%m-%d %H:%M:%S')}"

                 print(f"\nTempo do cliente {client_name} ({client_mac}) expirou! Tentando criar lembrete...")
                 self.info_label.text = f"Tempo de {client_name} expirou! Tentando criar lembrete..."

                 if PLYER_CALENDAR_AVAILABLE:
                     try:
                         calendar.create_event(
                             title=event_title,
                             description=event_description,
                             start_time=event_time,
                             end_time=event_time
                         )
                         print(f"Lembrete criado para {client_name} às {event_time.strftime('%H:%M:%S')}.")
                         self.info_label.text = f"Lembrete criado para {client_name}!"
                         client_data['calendar_event_created'] = True

                     except NotImplementedError:
                         print("Erro: Backend do Plyer Calendar não implementado para esta plataforma.")
                         self.info_label.text = "Erro no lembrete: Plyer não implementado."
                     except Exception as e:
                         print(f"Erro ao criar lembrete para {client_name}: {e}")
                         self.info_label.text = f"Erro ao criar lembrete para {client_name}: {e}"
                 else:
                     print("Plyer Calendar não disponível. Não foi possível criar lembrete.")
                     self.info_label.text = "Plyer Calendar não disponível."


        # Mover os clientes expirados e redesenhar se necessário ---
        if expired_clients_this_tick:
             self.clients_list = [client for client in self.clients_list if client not in expired_clients_this_tick]
             self.expired_clients_list.extend(expired_clients_this_tick)

             print(f"Movidos {len(expired_clients_this_tick)} cliente(s) para a lista de vencidos.")
             self.update_client_list_display()
             self.update_expired_list_display()
             return # Sai da função para evitar atualizar timers dos widgets antigos


        #Se nenhum cliente expirou nesta tick, atualizar os rótulos dos timers VISÍVEIS ---
        # Iteramos diretamente sobre a lista de rótulos de timer ativos
        for timer_label in list(self.active_timer_labels): # Itera sobre uma cópia
            # Verifica se o rótulo ainda está no layout (ainda visível na lista ativa)
            if timer_label.parent is None:
                 if timer_label in self.active_timer_labels:
                      self.active_timer_labels.remove(timer_label)
                 continue

            creation_time = getattr(timer_label, 'client_creation_time', None)

            if creation_time is None:
                 timer_label.text = "Timer: --:--:--"
                 continue

            elapsed_time = now - creation_time
            time_remaining = self.total_timer_duration - elapsed_time

            total_seconds = int(time_remaining.total_seconds())
            if total_seconds < 0:
                total_seconds = 0

            hours = total_seconds // 3600
            minutes = (total_seconds % 3600) // 60
            seconds = total_seconds % 60
            timer_text = f"Timer: {hours:02}:{minutes:02}:{seconds:02}"

            timer_label.text = timer_text


    def show_add_client_popup(self, instance):
        """Cria e exibe uma caixa de diálogo (Popup) para adicionar um novo cliente."""

        main_popup_layout = BoxLayout(orientation='vertical', spacing=10, padding=10)
        input_grid = GridLayout(cols=2, spacing=10, size_hint_y=None, height=220)

        input_grid.add_widget(Label(text='MAC:', halign='right', valign='middle'))
        self.mac_input = TextInput(hint_text='Endereço MAC', multiline=False)
        input_grid.add_widget(self.mac_input)

        input_grid.add_widget(Label(text='Senha:', halign='right', valign='middle'))
        self.senha_input = TextInput(hint_text='Sua senha', multiline=False, password=False)
        input_grid.add_widget(self.senha_input)

        input_grid.add_widget(Label(text='Nome:', halign='right', valign='middle'))
        self.nome_input = TextInput(hint_text='Nome do Cliente', multiline=False)
        input_grid.add_widget(self.nome_input)

        main_popup_layout.add_widget(input_grid)

        button_layout = BoxLayout(orientation='horizontal', spacing=10, size_hint_y=None, height=50)
        cancel_button = Button(text='Cancelar')
        button_layout.add_widget(cancel_button)
        add_button = Button(text='Adicionar Cliente')
        button_layout.add_widget(add_button)
        main_popup_layout.add_widget(button_layout)

        add_client_popup = Popup(title='Adicionar Novo Cliente',
                             content=main_popup_layout,
                             size_hint=(0.95, 0.85),
                             auto_dismiss=False)

        def on_add_client(instance):
            """Pega os dados dos inputs, verifica se já existe, adiciona (se não) e atualiza a exibição."""
            mac_address = self.mac_input.text.strip()
            password = self.senha_input.text.strip()
            user_name = self.nome_input.text.strip()

            if not mac_address or not password or not user_name:
                 print("Erro: Todos os campos devem ser preenchidos.")
                 self.info_label.text = 'Erro: Preencha todos os campos!'
                 return

            already_registered = False

            for client in self.clients_list:
                if client.get('mac') == mac_address and client.get('senha') == password:
                    already_registered = True
                    break

            if not already_registered:
                 for client in self.expired_clients_list:
                     if client.get('mac') == mac_address and client.get('senha') == password:
                         already_registered = True
                         break

            if already_registered:
                 print(f"\nCliente com MAC {mac_address} e Senha correspondente já cadastrado!")
                 self.info_label.text = "Cliente já cadastrado!"
                 add_client_popup.dismiss()
                 self.show_alert_screen(f"Cliente com MAC {mac_address}\nSenha correspondente já foi cadastrado antes.")
                 return

            new_client = {
                'mac': mac_address,
                'senha': password,
                'nome': user_name,
                'creation_time': datetime.datetime.now(),
                'calendar_event_created': False,
                'status': 'active'
            }

            self.clients_list.append(new_client)

            self.update_client_list_display()

            print(f"\nCliente adicionado: {user_name} ({mac_address}) criado em {new_client['creation_time'].strftime('%Y-%m-%d %H:%M:%S')}\n")
            self.info_label.text = f'Cliente "{user_name}" adicionado! Cronômetro iniciado.'

            add_client_popup.dismiss()

        def on_cancel(instance):
            """Fecha o popup sem adicionar."""
            print("Adição de cliente cancelada.")
            self.info_label.text = 'Adição de cliente cancelada'
            add_client_popup.dismiss()

        add_button.bind(on_press=on_add_client)
        cancel_button.bind(on_press=on_cancel)

        add_client_popup.open()


if __name__ == '__main__':
    MobileApp().run()
