import re

path = 'templates/recipe_planner.html'
with open(path, 'r', encoding='utf-8') as f:
    text = f.read()

text = text.replace('data.meals.forEach(meal => {', 
'''let htmlString = "";
                    data.meals.forEach((meal, i) => {''')

text = text.replace('budgetIdeasContainer.innerHTML += `', 'htmlString += `')

text = text.replace('''<div style="height: 150px; background-image: url('${imgSrc}');''', 
'''<div id="budget-img-${i}" style="height: 150px; background-image: url('${imgSrc}');''')

text = text.replace('''                              </div>
                          `;
                      });
                  } else {''', '''                              </div>
                          `;
                      });
                      
                      budgetIdeasContainer.innerHTML = htmlString;
                      
                      data.meals.forEach((meal, i) => {
                          const mealName = typeof meal === "string" ? meal : (meal.name || "Unknown");
                          fetch(`https://www.themealdb.com/api/json/v1/1/search.php?s=${encodeURIComponent(mealName)}`)
                              .then(r => r.json())
                              .then(md => {
                                  if (md && md.meals && md.meals[0] && md.meals[0].strMealThumb) {
                                      document.getElementById(`budget-img-${i}`).style.backgroundImage = `url('${md.meals[0].strMealThumb}/preview')`;
                                  } else {
                                      fetch(`/api/recipe/image?q=${encodeURIComponent(mealName)}`)
                                          .then(r => r.json())
                                          .then(proxy => {
                                              if (proxy.success && proxy.url) {
                                                  let img = new Image();
                                                  img.onload = () => { document.getElementById(`budget-img-${i}`).style.backgroundImage = `url('${proxy.url}')`; };
                                                  img.src = proxy.url;
                                              }
                                          }).catch(console.error);
                                  }
                              }).catch(console.error);
                      });
                  } else {''')

with open(path, 'w', encoding='utf-8') as f:
    f.write(text)
print("Updated successfully")