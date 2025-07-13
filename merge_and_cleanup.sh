#!/bin/bash

# Save current branch name
current_branch=$(git branch --show-current)

if [ "$current_branch" == "main" ]; then
    echo "❌ Already on main branch. Abort."
    exit 1
fi

echo "✅ Staging all changes..."
git add .

echo "✅ Committing changes..."
git commit -m "${1:-Auto commit}"

echo "✅ Switching to main..."
git checkout main

echo "✅ Pulling latest main..."
git pull origin main

echo "✅ Merging $current_branch into main..."
git merge $current_branch

echo "✅ Pushing to remote..."
git push origin main

echo "✅ Deleting local branch $current_branch..."
git branch -d $current_branch

read -p "✨ New feature branch name? " new_branch

if [ -z "$new_branch" ]; then
    echo "⚠️ No branch name given. Exiting."
    exit 0
fi

echo "✅ Creating and switching to new branch $new_branch..."
git checkout -b $new_branch

echo "🎉 Done! You're now on $new_branch"
