#!/bin/bash
# Delete All Franchises from gob-staging
# 
# ⚠️  WARNING: This will delete ALL franchise documents from the gob-staging database!
# This is a destructive operation and cannot be undone.

# Load environment variables
if [ -f .env.local ]; then
    export $(cat .env.local | grep -v '^#' | xargs)
elif [ -f .env ]; then
    export $(cat .env | grep -v '^#' | xargs)
fi

if [ -z "$MONGO_URI" ]; then
    echo "❌ MONGO_URI not found in environment variables"
    echo "   Set MONGO_URI in .env file or export it"
    exit 1
fi

# Extract database name from URI (should be gob-staging)
DB_NAME="gob-staging"

echo "🔗 Connecting to MongoDB..."
echo "📊 Database: $DB_NAME"
echo ""

# Use mongosh to delete all franchises
mongosh "$MONGO_URI" --eval "
use('$DB_NAME');
const count = db.franchises.countDocuments({});
print('📈 Current franchises count: ' + count + ' documents');
if (count > 0) {
    print('');
    print('⚠️  WARNING: This will delete ALL ' + count + ' franchise documents!');
    print('🗑️  Deleting all franchise documents...');
    const result = db.franchises.deleteMany({});
    print('✅ Deleted ' + result.deletedCount + ' franchise documents');
    const remaining = db.franchises.countDocuments({});
    print('📊 Final franchises count: ' + remaining + ' documents');
    if (remaining === 0) {
        print('');
        print('✅ Success! All franchise documents deleted from gob-staging');
        print('   Collection is now empty and ready for fresh data');
    }
} else {
    print('✅ Franchises collection is already empty.');
}
"
