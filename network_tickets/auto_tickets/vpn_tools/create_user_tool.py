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


#################################################### create user ########################################################################################
def call_create_user_api(vendor_name, vendor_email, phone_number, manager_id):
    url = f'{endpoint}/api/open/v1/user/create'
    header = {
        'Authorization': token,
    }
    payload = {
        'full_name': vendor_name,
        'email': vendor_email,
        'mobile': phone_number,
        'manager_ids': [manager_id],
        'department_id': department_id,
        'invite_type': 3,

    }
    try:
        response = requests.post(url, json=payload, headers=header)
        response.raise_for_status()
        result = response.json()
        # print(f'API Response: {result}')  # Debug: print the actual response
        
        # Check if 'data' key exists in the response
        if 'data' in result:
            if isinstance(result['data'], dict) and 'result' in result['data']:
                if result['data']['result'] == 'success':
                    return result['data']['id']
                else:
                    error_msg = result.get('message', 'Unknown error')
                    print(f'{vendor_name}: {error_msg}')
                    return False
            else:
                # 'data' exists but doesn't have 'result' key - might be a different response structure
                print(f'Unexpected response structure: {result}')
                return False
        else:
            # No 'data' key - check for error message or other structure
            if 'message' in result:
                print(f'{vendor_name}: {result["message"]}')
            else:
                print(f'Unexpected response format: {result}')
            return False
    except requests.exceptions.RequestException as e:
        print(f'{vendor_name}: {e}')
        return None
    except KeyError as e:
        print(f'KeyError: Missing key {e} in response: {result}')
        return None


def create_vpn_user_tool(wb):
    sheet = wb.active

    start_row = 4
    end_row = sheet.max_row
    print(f'end_row: {end_row}')

    if end_row < start_row:
        error_msg = f"No data found in Excel file. Expected data starting from row {start_row}."
        print(error_msg)
        exit(1)

    ticket_number_dic = {}
    manager_id_dic = {}
    vendor_name_dic = {}
    vendor_email_dic = {}
    phone_number_dic = {}

    for row in range(start_row, end_row + 1):
        print(f'row: {row}')

        ticket_number = sheet.cell(row=row, column=1).value
        manager_id = sheet.cell(row=row, column=2).value
        vendor_name = sheet.cell(row=row, column=3).value
        vendor_email = sheet.cell(row=row, column=4).value
        phone_number = sheet.cell(row=row, column=5).value

        if ticket_number is not None:
            ticket_number_dic[row] = str(ticket_number)
        else:
            print(f'Ticket number is not found in row {row}')
            exit(1)

        if phone_number is not None:
            if re.search(r'^[0-9]{11}$', str(phone_number)):
                phone_number_dic[row] = str(phone_number).replace(' ', '')
            else:
                print(f'Invalid phone number: {phone_number}')
                exit(1)
        else:
            print(f'Phone number is not found in row {row}')
            exit(1)

        if manager_id is not None:
            manager_id_dic[row] = manager_id.lower().replace(' ', '')
        else:
            print(f'Manager ID is not found in row {row}')
            exit(1)

        if vendor_name is not None:
            vendor_name_dic[row] = vendor_name.replace(' ', '')
        else:
            print(f'Vendor name is not found in row {row}')
            exit(1)

        if vendor_email is not None:
            if re.search(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', vendor_email):
                vendor_email_dic[row] = vendor_email
            else:
                print(f'Invalid email: {vendor_email}')
                exit(1)
        else:
            print(f'Vendor email is not found in row {row}')
            exit(1)

    res = {}
    for row in range(start_row, end_row + 1):
        user_id = call_create_user_api(vendor_name_dic[row], vendor_email_dic[row], phone_number_dic[row], manager_id_dic[row])
        if user_id:
            print(f'Successful to create an account for {vendor_name_dic[row]}')
            res[vendor_name_dic[row]] = user_id
        else:
            print(f'Failed to create an account for {vendor_name_dic[row]}')
    return res


if __name__ == '__main__':
    res = create_vpn_user_tool()
    print(f'res: {res}')