#include <string>
#include <vector>
#include <random>
#include <algorithm>
#include <sqlite3.h>


template<typename T>
/**
 * Calculates the sum of two values of type T.
 * 
 * @param a The first value to be added.
 * @param b The second value to be added.
 * @return The sum of a and b.
 */
T a_plus_b(T a, T b) {
    return a + b;
}


/**
 * Executes a SQL query on the provided SQLite database and returns the results 
 * as a vector of vector of strings, where each inner vector represents a row 
 * of the result set.
 * 
 * @param db A pointer to the SQLite database connection.
 * @param query The SQL query to be executed.
 * @return A vector of vectors containing the results of the query, each inner 
 *         vector representing a row and each string representing a column value.
 */
std::vector<std::vector<std::string>> sqlite(sqlite3* db, const std::string& query) {
    std::vector<std::vector<std::string>> results;
    sqlite3_stmt* stmt;

    if (sqlite3_prepare_v2(db, query.c_str(), -1, &stmt, nullptr) != SQLITE_OK) {
        return results;
    }

    while (sqlite3_step(stmt) == SQLITE_ROW) {
        std::vector<std::string> row;
        for (int i = 0; i < sqlite3_column_count(stmt); i++) {
            const unsigned char* text = sqlite3_column_text(stmt, i);
            if (text) {
                row.push_back(std::string(reinterpret_cast<const char*>(text)));
            } else {
                row.push_back("");
            }
        }
        results.push_back(row);
    }

    sqlite3_finalize(stmt);
    return results;
}


template<typename T, typename F>
/**
 * Compares two items using a provided key mapping function.
 * 
 * This function applies the `key_map` function to both `item1` and `item2`
 * and returns an integer indicating their relative ordering:
 * - A negative value if `item1` is less than `item2`
 * - A positive value if `item1` is greater than `item2`
 * - Zero if they are considered equal
 *
 * @param F key_map A function that maps items of type T to comparable values.
 * @param const T& item1 The first item to compare.
 * @param const T& item2 The second item to compare.
 * @return int An integer representing the comparison result.
 */
int compare(F key_map, const T& item1, const T& item2) {
    auto val1 = key_map(item1);
    auto val2 = key_map(item2);

    if (val1 < val2) return -1;
    if (val1 > val2) return 1;
    return 0;
}


/**
 * Generates a random string of specified length composed of 
 * lowercase and uppercase alphabetic characters.
 * 
 * @param length The desired length of the random alphabet string.
 * @return A string containing random alphabet characters of the specified length.
 */
std::string random_alphabets(int length) {
    static const std::string chars =
        "abcdefghijklmnopqrstuvwxyz"
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ";

    static std::random_device rd;
    static std::mt19937 generator(rd());
    static std::uniform_int_distribution<> distribution(0, chars.size() - 1);

    std::string result;
    result.reserve(length);

    for (int i = 0; i < length; ++i) {
        result += chars[distribution(generator)];
    }

    return result;
}