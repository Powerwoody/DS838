# imports:
from flask import Flask, render_template, request, jsonify, redirect, session, flash, url_for
import os
from google import genai
from dotenv import load_dotenv
import psycopg2
import json
from psycopg2.extensions import adapt

# Loading environment variables from .env file (stores the gimini API key):
load_dotenv()

# Configuring the Gemini API key:
api_key = os.getenv("GEMINI_API_KEY")

if not api_key: # if no api is set in the .env
    raise ValueError("GEMINI_API_KEY environment variable is not set. Please check your test.env file.")

client = genai.Client(api_key=api_key)

# Intilizing the Flask instance:
app = Flask(__name__)

# Setting the key for session mangement:
app.secret_key = "Shitty secret key"

@app.route('/')
def index():
    print(f"DEBUG: Session data before rendering index: {session}")
    # Getting the username from the session:
    username = session.get('email', '')
    return render_template('landing_page.html', username=username)

@app.route('/shopping_list')
def shopping_list():
    # Accessing the shopping list from the session if available:
    shopping_list_items = session.get('shopping_list', [])
    return render_template('shopping_list.html', shopping_list=shopping_list_items)

@app.route('/my_meals')
def my_meals():
    # Checking if user is logged in:
    if 'logged_in' not in session or not session['logged_in']:
        # Redirecting to login if not logged in:
        return redirect(url_for('login'))
    return render_template('my_meals.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    next_page = request.args.get('next', '/generator_page')
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        try:
            # Establishing the connection to the database:
            conn = psycopg2.connect(
                database="postgres",
                user="postgres",
                host="localhost",
                password="1234",
                port=5433,
            )
            cur = conn.cursor()

            # Checking if the user exists in the users table:
            cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
            user_exists = cur.fetchone()
            
            if user_exists:
                # Checking if the password is correct:
                cur.execute("SELECT 1 FROM users WHERE username = %s AND password = %s", (username, password))
                password_correct = cur.fetchone()
                
                if password_correct:
                    # User is authenticated, and the session variables are set:
                    session['logged_in'] = True
                    session['email'] = username
                    return redirect(next_page)
                else:
                    cur.close()
                    conn.close()
                    return render_template('login.html', error_message="Invalid password")
            else:
                cur.close()
                conn.close()
                return render_template('login.html', error_message="User does not exist, please sign up")
        except psycopg2.OperationalError as e:
            # Connection failed
            return render_template('login.html', error_message="Database connection failed. Please try again later.")
    else:
        success_message = request.args.get('success_message', '')
        return render_template('login.html', success_message=success_message)

@app.route("/logout")
def logout():
    # clear session
    session.clear()
    return redirect("/")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form["username"]
        password = request.form["password"]
        confirm_password = request.form["confirm_password"]

        if password != confirm_password:
            return render_template('register.html', error_message="Passwords do not match")
        
        try:
            print("DEBUG: Attempting database connection")
            conn = psycopg2.connect(
                database="postgres",
                user="postgres",
                host="localhost",
                password="1234",
                port=5433,
            )
            
            print("DEBUG: Database connection successful")
            cur = conn.cursor()
            
            print("DEBUG: Checking if user exists")
            cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
            user_exists = cur.fetchone()
            
            if user_exists:
                cur.close()
                conn.close()
                return render_template('register.html', error_message="Username already exists")
            
            cur.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
            
            conn.commit()
            
            cur.close()
            conn.close()
            return redirect(url_for('login', success_message="Registration successful"))
        except psycopg2.OperationalError as e:
            return render_template('register.html', error_message="Database connection failed. Please try again later.")
        except Exception as e:
            return render_template('register.html', error_message=f"Registration failed: {str(e)}")
    else:
        # Handling the GET request - just showing the register form:
        return render_template('register.html')

@app.route('/settings', methods=['GET', 'POST'])
def settings():
    # Getting username from session:
    username = session.get('email', '')
    
    if 'logged_in' not in session or not session['logged_in']:
        return redirect(url_for('login', next=url_for('settings')))
    
    if request.method == 'POST':
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']
        
        if new_password != confirm_password:
            return render_template('settings.html', username=username, error_message="New passwords do not match")
        
        try:
            # Connecting to the postgresql database:
            conn = psycopg2.connect(
                database="postgres",
                user="postgres",
                host="localhost",
                password="1234",
                port=5433,
            )
            cur = conn.cursor()
            
            # Verifying the current password:
            cur.execute(
                "SELECT 1 FROM users WHERE username = %s AND password = %s",
                (username, current_password)
            )
            password_correct = cur.fetchone()
            
            if not password_correct:
                cur.close()
                conn.close()
                return render_template('settings.html', username=username, error_message="Current password is incorrect")
            
            # Updating the password:
            cur.execute(
                "UPDATE users SET password = %s WHERE username = %s",
                (new_password, username)
            )
            
            conn.commit()
            cur.close()
            conn.close()
            
            return render_template('settings.html', username=username, success_message="Password updated successfully")
            
        except psycopg2.OperationalError as e:
            return render_template('settings.html', username=username, error_message="Database connection failed. Please try again later.")
        except Exception as e:
            return render_template('settings.html', username=username, error_message=f"Error: {str(e)}")
    
    return render_template('settings.html', username=username)

@app.route('/generator_page')
def generator_page():
    # Getting the username from session:
    username = session.get('email', '')
    return render_template('generator_page.html', username=username)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/save-meal', methods=['POST'])
def save_meal():
    # Checking if the user is logged in:
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': 'You must be logged in to save meals'}), 401
    
    # Getting the meal data from request:
    meal_data = request.json
    
    if not meal_data or 'title' not in meal_data or 'ingredients' not in meal_data or 'recipe' not in meal_data:
        return jsonify({'success': False, 'message': 'Invalid meal data format'}), 400
    
    try:
        # Connecting to the postgresql database:
        conn = psycopg2.connect(
            database="postgres",
            user="postgres",
            host="localhost",
            password="1234",
            port=5433,
        )
    
        cur = conn.cursor()
        
        # Converting the items_list into a TEXT column instead of an ARRAY:
        item_list_json = json.dumps(meal_data['ingredients'])
        
        # Checking if this meal already exists for the user:
        cur.execute(
            "SELECT 1 FROM user_meals WHERE username = %s AND meal_title = %s", 
            (session['email'], meal_data['title'])
        )
        meal_exists = cur.fetchone()
        
        # First, trying to get the structure of the table to see what the items_list column type is:

        cur.execute("SELECT column_name, data_type FROM information_schema.columns WHERE table_name = 'user_meals'")
        columns = cur.fetchall()

            
        if meal_exists:
            # Updating existing meal:
            try:
                cur.execute(
                    "UPDATE meals SET meal_items = %s::json, meal_des = %s WHERE username = %s AND meal_title = %s",
                    (item_list_json, meal_data['recipe'], session['email'], meal_data['title'])
                )
            except Exception as e:
                cur.execute(
                    "UPDATE user_meals SET meal_items = %s, meal_des = %s WHERE username = %s AND meal_title = %s",
                    (item_list_json, meal_data['recipe'], session['email'], meal_data['title'])
                )
        else:
            # Inserting new meal:
            try:
                cur.execute(
                    "INSERT INTO user_meals (username, meal_title, meal_items, meal_des) VALUES (%s, %s, %s::json, %s)",
                    (session['email'], meal_data['title'], item_list_json, meal_data['recipe'])
                )
            except Exception as e:
                cur.execute(
                    "INSERT INTO user_meals (username, meal_title, meal_items, meal_des) VALUES (%s, %s, %s, %s)",
                    (session['email'], meal_data['title'], item_list_json, meal_data['recipe'])
                )
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'message': 'Meal saved successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f"Database error: {str(e)}"}), 500

@app.route('/get-saved-meals', methods=['GET'])
def get_saved_meals():
    # Checking if user is logged in:
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': 'You must be logged in to view saved meals'}), 401
    
    try:
        # Connecting to the postgresql database:
        conn = psycopg2.connect(
            database="postgres",
            user="postgres",
            host="localhost",
            password="1234",
            port=5433,
        )
        
        cur = conn.cursor()
        
        # Getting the search query parameter if it exists:
        search_query = request.args.get('search', '')
        
        # Getting all meals for the logged-in user:
        if search_query:
            # Searching for meals with matching titles:
            query = "SELECT meal_title, meal_items, meal_des FROM user_meals WHERE username = %s AND meal_title ILIKE %s"
            params = (session['email'], f"%{search_query}%")
            cur.execute(query, params)
        else:
            # Getting all the meals for the user:
            query = "SELECT meal_title, meal_items, meal_des FROM user_meals WHERE username = %s"
            params = (session['email'],)
            cur.execute(query, params)
        
        # Checking if the query returned any rows:
        rows = cur.fetchall()
        
        meals = []
        for row in rows:
            # Handling different possible types for ingredients:
            ingredients = row[1]
            
            if isinstance(ingredients, list):
                pass
            elif isinstance(ingredients, str):
                try:
                    ingredients = json.loads(ingredients)
                except json.JSONDecodeError as e:
                    ingredients = [ingredients]
            else:
                ingredients = [str(ingredients)]
            
            meals.append({
                'title': row[0],
                'ingredients': ingredients,
                'recipe': row[2]
            })
        
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'meals': meals})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f"Database error: {str(e)}"}), 500

@app.route('/generate-meals', methods=['POST'])
def generate_meals():
    # Getting the filter data from request:
    filter_data = request.json
    
    # Extracting the filter values:
    meal_types = filter_data.get('mealTypes', [])
    protein_types = filter_data.get('proteinTypes', [])
    kulhydrat_types = filter_data.get('kulhydratTypes', [])
    
    # Creating prompt for Gemini:
    prompt = f"""
    Generate 3 meal recipes based on the following criteria: (Response has to be in english)
    
    Meal types: {', '.join(meal_types)}
    Protein types: {', '.join(protein_types)}
    Carbohydrate types: {', '.join(kulhydrat_types)}
    
    For each meal, provide:
    1. A title
    2. A list of ingredients with approximate quantities
    3. A brief recipe with cooking instructions
    
    Format the response as a JSON object with the following structure:
    {{
        "meals": [
            {{
                "title": "Meal Title",
                "ingredients": ["Ingredient 1", "Ingredient 2", ...],
                "recipe": "Step-by-step cooking instructions..."
            }},
            ...
        ]
    }}
    
    Make sure the meals are varied and appropriate for the selected criteria.
    """
    
    try:
        # Calling Gemini API using the updated client approach:
        response = client.models.generate_content(
            model="gemini-1.5-flash",  # Using a current model:
            contents=prompt
        )
        
        # Parsing the response:
        result = response.text
        
        # If the response is wrapped in code blocks, extracting just the JSON part:
        if "```json" in result:
            result = result.split("```json")[1].split("```")[0].strip()
        elif "```" in result:
            result = result.split("```")[1].split("```")[0].strip()
            
        # Converting string to JSON if needed:
        if isinstance(result, str):
            try:
                result = json.loads(result)
            except json.JSONDecodeError:
                # If the JSON parsing fails, creating a structured response manually:
                return jsonify({
                    "meals": [
                        {
                            "title": "Error parsing API response",
                            "ingredients": ["Please try again"],
                            "recipe": "The AI generated an invalid response format. Please try again with different filters."
                        } for _ in range(3)
                    ]
                })
        
        return jsonify(result)
        
    except Exception as e:
        return jsonify({
            "meals": [
                {
                    "title": f"Error: {str(e)}",
                    "ingredients": ["Please try again"],
                    "recipe": "There was an error generating meals. Please check your API key and try again."
                } for _ in range(3)
            ]
        }), 500

@app.route('/delete-meal', methods=['POST'])
def delete_meal():
    # Checking if user is logged in:
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': 'You must be logged in to delete meals'}), 401
    
    # Getting meal data from request:
    meal_data = request.json
    
    if not meal_data or 'title' not in meal_data:
        return jsonify({'success': False, 'message': 'Invalid meal data format'}), 400
    
    try:
        # Connecting to database:
        conn = psycopg2.connect(
            database="postgres",
            user="postgres",
            host="localhost",
            password="1234",
            port=5433,
        )
        
        cur = conn.cursor()
        
        # Deleting the meal:
        cur.execute(
            "DELETE FROM user_meals WHERE username = %s AND meal_title = %s", 
            (session['email'], meal_data['title'])
        )
        
        rows_deleted = cur.rowcount
        
        conn.commit()
        cur.close()
        conn.close()
        
        if rows_deleted > 0:
            return jsonify({'success': True, 'message': 'Meal deleted successfully'})
        else:
            return jsonify({'success': False, 'message': 'Meal not found'}), 404
    
    except Exception as e:
        return jsonify({'success': False, 'message': f"Database error: {str(e)}"}), 500

@app.route('/add-to-shopping-list', methods=['POST'])
def add_to_shopping_list():
    # Checking if user is logged in:
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': 'You must be logged in to add to shopping list'}), 401
    
    # Getting the meal data from request:
    meal_data = request.json
    
    if not meal_data or 'title' not in meal_data:
        return jsonify({'success': False, 'message': 'Invalid meal data format'}), 400
    
    try:
        # Connecting to the postgresql database:
        conn = psycopg2.connect(
            database="postgres",
            user="postgres",
            host="localhost",
            password="1234",
            port=5433,
        )
        
        cur = conn.cursor()
        
        # Getting the meal's ingredients:
        cur.execute(
            "SELECT meal_items FROM user_meals WHERE username = %s AND meal_title = %s", 
            (session['email'], meal_data['title'])
        )
        
        result = cur.fetchone()
        cur.close()
        conn.close()
        
        if not result:
            return jsonify({'success': False, 'message': 'Meal not found'}), 404
        
        # Parsing ingredients from JSON string if needed:
        ingredients = result[0]
        if isinstance(ingredients, str):
            try:
                ingredients = json.loads(ingredients)
            except json.JSONDecodeError:
                ingredients = [ingredients]
        elif not isinstance(ingredients, list):
            ingredients = [str(ingredients)]
        
        # Storing in session for the shopping list page:
        session['shopping_list'] = ingredients
        
        return jsonify({
            'success': True, 
            'message': 'Ingredients added to shopping list',
            'ingredients': ingredients
        })
    
    except Exception as e:
        return jsonify({'success': False, 'message': f"Database error: {str(e)}"}), 500

@app.route('/clear-shopping-list', methods=['POST'])
def clear_shopping_list():
    # Checking if user is logged in:
    if 'logged_in' not in session or not session['logged_in']:
        return jsonify({'success': False, 'message': 'You must be logged in to clear shopping list'}), 401
    
    try:
        # Removing shopping list from session:
        if 'shopping_list' in session:
            session.pop('shopping_list')
        
        return jsonify({'success': True, 'message': 'Shopping list cleared successfully'})
    
    except Exception as e:
        return jsonify({'success': False, 'message': f"Error: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(host='127.0.0.1', port=8000, debug=True)