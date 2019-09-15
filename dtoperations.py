import re
from datetime import datetime, time


# funkcja eksportująca listę do pliku
def to_file(list_for_export, output_path):
    """ Writes list into a file of given file path 
    
    Parameters: list (list), path (string)
    Returns: file of \n seperated list items
    """
    
    with open(output_path, "w") as f:
        for element in list_for_export:
            f.write(element+'\n')
            

# funkcja sprawdzająca poprawność formatu godziny            
def time_check(raw_time):
    """ Validates time format with and without AM/PM
    
    Parameters: time (string)
    Returns: input string if it's valid 
             or empty string if it's not
    """
    
    if "m" in raw_time or "M" in raw_time:
        try:
            # odrzuca nieprawidłowe czasy np. 23:45AM 
            datetime.strptime(raw_time, "%I:%M%p").time()
            return raw_time
        except:
            return ""    
    else:
        return raw_time   
    
            
# funkcja parsująca string czasu do objektu datetime
def time_format(raw_time):
    """ Converts time string to datetime.time() object """
    
    raw_time = time_check(raw_time)

    if "m" in raw_time or "M" in raw_time:
        return datetime.strptime(raw_time, "%I:%M%p").time()
    elif raw_time != "":
        return datetime.strptime(raw_time, "%H:%M").time()
    else:
        # jeśli brak informacji o czasie zwraca pusty string
        return ""

    
def dtfind(input_file_path, raw_str=False):
    """ Searches for dates in given file
    
    Parameters: input file path (string), 
                optional raw_str (bool)
                
    Returns: list of datetime object tuples (date, time)
             if raw_str is False. If True, returns list of
             strings of connected date and time
    """
    
    with open(input_file_path) as f:
        content = f.read()
        
    regex = r"(?:(?:((?:Jan|Apr|Feb|Mar|May|Jun|Jul|Aug|Oct|Sep|Nov|Dec) "
            "(?:[1-9]|[12][0-9]|3[01]) \d*))|(?:([0-1][0-9](?:\/)"
            "(?:0[1-9]|[12][0-9]|3[01])(?:\/)\d*))|(?:((?:0[1-9]|[12][0-9]|3[01])"
            "(?:-)[0-1][0-9](?:-)\d*)))(?: |)((?:(?:0[0-9]|[0-9]|1[0-9]|2[0-3]):"
            "(?:0[0-9]|[1-4][0-9]|5[0-9])|)(?:AM|PM|am|pm|))"
            
    # rozpakowanie wychwyconych regexów do listy 4-elementowych tupli
    # w indeksach 0 lub 1 lub 2 znajdują się trzy konkretne formaty dat
    # w indeksie 3 znajdują się różne formaty godziny lub brak godziny
    raw_datetime = re.finditer(regex, content, re.MULTILINE)
    raw_datetime_list = []

    for match in raw_datetime:
        raw_datetime_list.append(match.groups())
    
    if raw_str == True:
        raw_strings = []
        for match in raw_datetime_list:
            
            date_string = ''.join(filter(lambda x: x is not None, match[:-1]))

            time_string = time_check(match[3])            
            if time_string == '':
                raw_strings.append(date_string)
                
            else:
                raw_strings.append(date_string+" "+time_string)
            
        return raw_strings
    
    # tworzy listę sparsowanych tupli (data, czas)
    datetime_list = []

    for raw in raw_datetime_list:
        date_obj = None        
        if raw[0] != None:
            date_obj = datetime.strptime(raw[0], "%b %d %Y")
        elif raw[1] != None:
            date_obj = datetime.strptime(raw[1], "%m/%d/%Y")
        elif raw[2] != None:
            date_obj = datetime.strptime(raw[2], "%d-%m-%Y")
        else:
            raise ValueError("Błędne dane")
        datetime_list.append((date_obj, time_format(raw[3])))

    return datetime_list


def dtformat(input_file_path, output_file_path=None, fmt="%d-%m-%Y"):
    """ Converts dates of given file
    
    Parameters: input file path (string), 
                optional output file path (string)
                optional custom formating (string)
                
    Returns: list of strings of formated dates and time
             or file of \n seperated list items
             if output file path is defined
    """
    
    datetime_list = dtfind(input_file_path)
    datetime_formated = []
    
    for dt in datetime_list:
        str_date = dt[0].strftime(fmt)
        
        if dt[1] == '':   
            str_time = ''
        else:
            str_time = " " + dt[1].strftime("%H:%M")
        datetime_formated.append(str_date+str_time)
    
    if output_file_path == None:
        return datetime_formated
    
    else:
        return to_file(datetime_formated, output_file_path)

    
def dtreplace(input_file_path, output_file_path, fmt="%d-%m-%Y"):
    """ Creates new file with formated date and time
    
    Parameters: input file path (string),
                output file path (string),
                optional custom formating (string)
                
    Returns: file with formated dates and time
    
    """
    
    custom_format = fmt
    input_dates = dtfind(input_file_path, raw_str=True)
    input_dates_formatted = dtformat(input_file_path, fmt=custom_format)

    with open(input_file_path) as f:
        content = f.read()
        
    for i in range(len(input_dates)):
        if input_dates[i] in content:
            if input_dates_formatted[i] == '':
                continue
            else:
                content = content.replace(input_dates[i], input_dates_formatted[i], 1)

    with open(output_file_path, 'w') as f:
        f.write(content)
