import urllib.request
import json
import traceback
import logging

logformat = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
logging.basicConfig(format=logformat, level=logging.INFO,
                    filename='./ubisoft_status_bot.log', filemode='w')


class UbisoftServerStatus:
    def __init__(self, game_id):

        url_base = 'https://game-status-api.ubisoft.com/v1/instances?appIds={game_id}'

        self.url = url_base.format(game_id=game_id)

    def __call__(self, timeout=5):

        with urllib.request.urlopen(self.url, timeout=timeout) as request:
            json_data = json.load(request)
            return json_data[0]

class UbisoftServerStatusPoller:
    def __init__(self, status_checker, print_on_first_run = False):
        self.status_checker = status
        self.last_seen_status = None
        self.print_on_first_run = print_on_first_run

    def __call__(self):
        message = ''
        try:
            current_status = self.status_checker()['Status']

            if self.last_seen_status is not None:

                if current_status != self.last_seen_status:
                    message = f"Server status change from {self.last_seen_status} to {current_status}."
            elif self.print_on_first_run:
                message = f"Good morning! Server status this lovely day is: {current_status}."

            self.last_seen_status = current_status
        except Exception as e:
            # Something went wrong
            logging.error(f"Error while getting server status:  {str(e)}.\n" \
                          f"Stack trace: {traceback.format_exc()}")

        return len(message) > 0, message


def make_rainbow_six_siege_poller(print_on_first_run = False):
    status_checker = UbisoftServerStatus(GAME_IDS['Rainbow Six Siege'])
    poller = UbisoftServerStatusPoller(status_checker, print_on_first_run=print_on_first_run)
    return poller


GAME_IDS = {
    "Rainbow Six Siege" : 'e3d5ea9e-50bd-43b7-88bf-39794f4e3d40',
}

    
if __name__ == '__main__':
    status = UbisoftServerStatus(GAME_IDS['Rainbow Six Siege'])

    # Json-infy it again for pretty print
    print(json.dumps(status(), indent=4))

    # Run it four times
    poller = UbisoftServerStatusPoller(status, print_on_first_run=True)
    for _ in range(4):
        do_display, message = poller()
        if do_display:
            print(message)

