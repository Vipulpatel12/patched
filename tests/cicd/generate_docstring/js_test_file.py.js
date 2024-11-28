
/**
 * Adds two numbers together.
 * @param {number}  a - The first number to add.
 * @param {number}  b - The second number to add.
 * @returns {number} The sum of the two numbers.
 */
function a_plus_b(a, b) {
    return a + b;
}

/**
 * Compares two objects based on a specified key from a keymap.
 * @param {string} keymap - The key used for comparison in the objects.
 * @param {Object} a - The first object to compare.
 * @param {Object} b - The second object to compare.
 * @returns {number} A negative number if 'a' is less than 'b', a positive number if 'a' is greater than 'b', and 0 if they are equal.
 */
const compare = function (keymap, a, b) {
    if (a[keymap] < b[keymap]) {
        return -1;
    } else if (a[keymap] > b[keymap]) {
        return 1;
    } else {
        return 0;
    }
}

/**
 * Executes a SQLite query in a serialized manner and applies the callback to each row returned.
 * @param {Object} db - The SQLite database connection object.
 * @param {string} query - The SQL query to be executed on the database.
 * @param {function} callback - The function to be called for each row retrieved by the query.
 * @returns {void} This function does not return a value.
 */
const sqlite = (db, query, callback) => {
    db.serialize(function () {
        db.each(query, callback);
    });
}