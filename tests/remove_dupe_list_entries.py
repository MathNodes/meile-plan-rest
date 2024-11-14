def remove_duplicates(test):
    
    for key in test:
        test[key] = [item for item in test[key] if sum(item in test[other_key] for other_key in test if other_key != key) == 0]
        test[key] = list(set(test[key]))
    

test = {
    'key1': [1, 2, 3, 4],
    'key2': [3,2,2, 4, 5, 6, 3, 6],
    
}

remove_duplicates(test)
print(test)