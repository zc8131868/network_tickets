import requests
import openpyxl
import re



#################################################### get token ########################################################################################
endpoint = 'https://vpn.hk.chinamobile.com:8443'
access_key_id = 'kGDarBmLTGmYzVtlPxpH'
access_key_secret = 'wvYDfEVOaFlKUgnbEmCJoanojdiTBTjCXmvnLKde'

url = f'{endpoint}/api/open/v1/token'

payload = {
    'access_key_id': access_key_id,
    'access_key_secret': access_key_secret
}

try:
    response = requests.post(url, json=payload)
    response.raise_for_status()
    res = response.json()
    print(res)
    token = res['data']['access_token']
except requests.exceptions.RequestException as e:
    print(f'Error: {e}')

#################################################### get department id ########################################################################################
url = f'{endpoint}/api/open/v1/department/get_id'
# print(f'token: {token}')
header = {
    'Authorization': token,
}
payload = {
    'name': "Vendor",
}

try:
    response = requests.post(url, json=payload, headers=header)
    response.raise_for_status()
    department_id = response.json()['data']['id']
    print(f'department_id: {department_id}')
except requests.exceptions.RequestException as e:
    print(f'Error: {e}')

##################################################### delete user ########################################################################################
def call_delete_user_api(vendor_email):
    vendor_openid = get_manager_id(vendor_email)
    url = f'{endpoint}/api/open/v1/user/status/update'
    header = {
        'Authorization': token,
    }
    payload = {
        'id': vendor_openid,
        'status': 'offline',
    }
    try:
        response = requests.post(url, json=payload, headers=header)
        response.raise_for_status()
        result = response.json()
        if result['data']['result'] == 'success':
            return 'success'
        else:
            return result['message']
    except requests.exceptions.RequestException as e:
        print(f'Error: {e}')
        return None
    except KeyError as e:
        print(f'KeyError: Missing key {e} in response: {result}')
        return None

if __name__ == '__main__':
    res = call_delete_user_api('ou_wDV345vjaW')
    if res == 'success':
        print('User deleted successfully')
    else:
        print(f'Error: {res}')


#####################################################get manager id######################################################################################
def get_manager_id(manager_email):
    url = f'{endpoint}/api/open/v1/user/get_id'
    header = {
        'Authorization': token,
    }

    payload = {
        'email': manager_email,
    }
    try:
        response = requests.post(url, json=payload, headers=header)
        response.raise_for_status()
        res = response.json()
        return res['data']['id']
    except requests.exceptions.RequestException as e:
        print(f'Error: {e}')    
        return None