clear

echo "Step 1: Stop existing Ikke instances..."
killall ikke

echo "Step 2: Clean the old distribution..."
cd /Users/laffra/PycharmProjects/Ikke && rm -rf dist

echo "Step 3: Create new distribution..."
pyinstaller pyinstaller.spec

echo "Step 4: Launch to test..."
open dist/ikke.app