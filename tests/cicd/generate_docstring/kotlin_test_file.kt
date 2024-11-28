package org.example

import java.sql.Connection
import java.sql.ResultSet
import kotlin.random.Random


/**
 * This function takes two numbers of the same type and returns their sum as a Double.
 * 
 * @param a The first number to be added.
 * @param b The second number to be added.
 * @return The sum of the two input numbers as a Double.
 */
fun <T : Number> aPlusB(a: T, b: T): Double = a.toDouble() + b.toDouble()


/**
 * Executes a SQL query on the provided SQLite database connection and returns the results 
 * as a list of rows, where each row is represented as a list of column values.
 * 
 * @param db The SQLite database connection to execute the query on.
 * @param query The SQL query string to be executed.
 * @return A list of rows, each represented as a list of column values from the result set.
 */
fun sqlite(db: Connection, query: String): List<List<Any?>> {
    db.createStatement().use { statement ->
        statement.executeQuery(query).use { resultSet ->
            val results = mutableListOf<List<Any?>>()
            val columnCount = resultSet.metaData.columnCount

            while (resultSet.next()) {
                val row = mutableListOf<Any?>()
                for (i in 1..columnCount) {
                    row.add(resultSet.getObject(i))
                }
                results.add(row)
            }
            return results
        }
    }
}


/**
 * Compares two items based on a specified key mapping function.
 * 
 * This function takes a key mapping function and two items as parameters,
 * and returns an integer indicating their relative order based on the 
 * values produced by the key mapping function.
 * 
 * @param keyMap A function that maps an item of type T to a comparable 
 * value of type R.
 * @param item1 The first item of type T to compare.
 * @param item2 The second item of type T to compare.
 * @return A negative integer if item1 is less than item2, a positive integer 
 * if item1 is greater than item2, and zero if they are equal.
 */
fun <T, R : Comparable<R>> compare(keyMap: (T) -> R, item1: T, item2: T): Int {
    return when {
        keyMap(item1) < keyMap(item2) -> -1
        keyMap(item1) > keyMap(item2) -> 1
        else -> 0
    }
}


/**
 * Generates a random string of alphabets of specified length.
 * 
 * @param length The desired length of the random alphabet string.
 * @return A string containing randomly selected alphabets of the specified length.
 */
fun randomAlphabets(length: Int): String {
    val charPool = ('a'..'z') + ('A'..'Z')
    return (1..length)
        .map { charPool[Random.nextInt(0, charPool.size)] }
        .joinToString("")
}