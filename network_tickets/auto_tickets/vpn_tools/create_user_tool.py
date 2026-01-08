import requests
import openpyxl
import re

# Phone number validation patterns
# Supports: 11-digit mainland China numbers, +852/HK 8-digit, +86/86 11-digit
PHONE_PATTERN = re.compile(
    r'^('
    r'\+?852\d{8}|'      # Hong Kong: +85212345678 or 85212345678
    r'\+?86\d{11}|'      # China with country code: +8613800138000 or 8613800138000
    r'\d{11}'            # Mainland China: 13800138000
    r')$'
)



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
#################################################### create user ########################################################################################
def call_create_user_api(vendor_name, vendor_email, phone_number, manager_email):
    manager_id = get_manager_id(manager_email)
    
    if manager_id is None:
        print(f'Failed to get manager id for {manager_email}')
        return False
    
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
                    return {'success': True, 'user_id': result['data']['id'], 'error': None}
                else:
                    error_msg = result.get('message', 'Unknown error')
                    print(f'{vendor_name}: {error_msg}')
                    return {'success': False, 'user_id': None, 'error': f'{vendor_name}: {error_msg}'}
            else:
                # 'data' exists but doesn't have 'result' key - might be a different response structure
                error_msg = f'Unexpected response structure: {result}'
                print(error_msg)
                return {'success': False, 'user_id': None, 'error': f'{vendor_name}: {error_msg}'}
        else:
            # No 'data' key - check for error message or other structure
            if 'message' in result:
                error_msg = f'{vendor_name}: {result["message"]}'
                print(error_msg)
                return {'success': False, 'user_id': None, 'error': error_msg}
            else:
                error_msg = f'Unexpected response format: {result}'
                print(error_msg)
                return {'success': False, 'user_id': None, 'error': f'{vendor_name}: {error_msg}'}
    except requests.exceptions.RequestException as e:
        error_msg = f'{vendor_name}: {e}'
        print(error_msg)
        return {'success': False, 'user_id': None, 'error': error_msg}
    except KeyError as e:
        error_msg = f'KeyError: Missing key {e} in response: {result}'
        print(error_msg)
        return {'success': False, 'user_id': None, 'error': f'{vendor_name}: {error_msg}'}


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
    manager_email_dic = {}
    vendor_name_dic = {}
    vendor_email_dic = {}
    phone_number_dic = {}
    validation_errors = []

    for row in range(start_row, end_row + 1):
        print(f'row: {row}')

        ticket_number = sheet.cell(row=row, column=1).value
        manager_email = sheet.cell(row=row, column=2).value
        vendor_name = sheet.cell(row=row, column=3).value
        vendor_email = sheet.cell(row=row, column=4).value
        phone_number = sheet.cell(row=row, column=5).value

        # Skip empty rows
        if not any([ticket_number, manager_email, vendor_name, vendor_email, phone_number]):
            continue

        row_errors = []
        
        if ticket_number is not None:
            ticket_number_dic[row] = str(ticket_number)
        else:
            error_msg = f'Row {row}: Ticket number is not found'
            print(error_msg)
            row_errors.append(error_msg)

        if phone_number is not None:
            # Clean phone number (remove spaces, dashes, parentheses)
            cleaned_phone = re.sub(r'[\s\-\(\)]', '', str(phone_number))
            
            # Validate phone number format
            if PHONE_PATTERN.match(cleaned_phone):
                phone_number_dic[row] = cleaned_phone
            else:
                vendor_display = vendor_name if vendor_name else f'Row {row}'
                error_msg = f'{vendor_display}: 手机号格式错误 (Invalid phone number format: {phone_number}). Expected: 11-digit mainland China number, +852 + 8-digit HK number, or +86 + 11-digit China number'
                print(error_msg)
                row_errors.append(error_msg)
        else:
            vendor_display = vendor_name if vendor_name else f'Row {row}'
            error_msg = f'{vendor_display}: Phone number is not found'
            print(error_msg)
            row_errors.append(error_msg)

        if manager_email is not None:
            if re.search(r'^[a-zA-Z0-9._%+-]+@hk\.chinamobile\.com$', manager_email):
                manager_email_dic[row] = manager_email
            else:
                error_msg = f'Row {row}: Invalid email format ({manager_email})'
                print(error_msg)
                row_errors.append(error_msg)
        else:
            error_msg = f'Row {row}: Manager email is not found'
            print(error_msg)
            row_errors.append(error_msg)


        if vendor_name is not None:
            vendor_name_dic[row] = vendor_name.replace(' ', '')
        else:
            error_msg = f'Row {row}: Vendor name is not found'
            print(error_msg)
            row_errors.append(error_msg)

        if vendor_email is not None:
            if re.search(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', vendor_email):
                vendor_email_dic[row] = vendor_email
            else:
                vendor_display = vendor_name if vendor_name else f'Row {row}'
                error_msg = f'{vendor_display}: Invalid email format ({vendor_email})'
                print(error_msg)
                row_errors.append(error_msg)
        else:
            vendor_display = vendor_name if vendor_name else f'Row {row}'
            error_msg = f'{vendor_display}: Vendor email is not found'
            print(error_msg)
            row_errors.append(error_msg)
        
        # Only add row to processing if no validation errors
        if row_errors:
            validation_errors.extend(row_errors)
            # Remove row from dictionaries if it was partially added
            ticket_number_dic.pop(row, None)
            manager_email_dic.pop(row, None)
            vendor_name_dic.pop(row, None)
            vendor_email_dic.pop(row, None)
            phone_number_dic.pop(row, None)

    res = {}
    errors = []
    
    # Add validation errors first
    errors.extend(validation_errors)
    
    # Process valid rows
    for row in range(start_row, end_row + 1):
        if row not in vendor_name_dic:
            continue  # Skip rows with validation errors
        
        result = call_create_user_api(vendor_name_dic[row], vendor_email_dic[row], phone_number_dic[row], manager_email_dic[row])
        if result['success']:
            print(f'Successful to create an account for {vendor_name_dic[row]}')
            res[vendor_name_dic[row]] = result['user_id']
        else:
            error_msg = result['error'] or f'Failed to create an account for {vendor_name_dic[row]}'
            print(error_msg)
            errors.append(error_msg)
    
    return {'success': res, 'errors': errors}


if __name__ == '__main__':
    res = create_vpn_user_tool()
    print(f'res: {res}')