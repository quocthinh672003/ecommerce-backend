'use strict'

const mongoose = require('mongoose')

class Database {
    constructor() {
        this.connect()
    }

    connect(type = 'mongodb') {
        if (1 === 1) {
            mongoose.set('debug', true)
            mongoose.set('debug', { color: true })

            mongoose.connect(process.env.MONGODB_URL)
                .then(() => console.log('Connected to MongoDB'))
                .catch(err => console.log(err))
        }
    }
}

module.exports = new Database()