import requests
from bs4 import BeautifulSoup
from typing import List, Dict, Optional

class KrishaScraper:
    """Scraper for krisha.kz website"""
    
    def __init__(self):
        self.base_url = "https://krisha.kz"
        
    def get_apartments(self, city: str, rooms: List[int], max_price: float) -> List[Dict]:
        """
        Scrape apartments from krisha.kz
        
        Args:
            city (str): City to search in
            rooms (List[int]): List of acceptable room numbers
            max_price (float): Maximum price
            
        Returns:
            List[Dict]: List of apartments matching criteria
        """
        apartments = []
        
        for room in rooms:
            url = f"{self.base_url}/arenda/kvartiry/{city}/?das[live.rooms]={room}&price[to]={max_price}"
            
            try:
                response = requests.get(url, headers={'User-Agent': 'Mozilla/5.0'})
                soup = BeautifulSoup(response.text, 'html.parser')
                
                listings = soup.find_all('div', class_='a-card__header')
                
                for listing in listings:
                    link = listing.find('a')
                    if link:
                        apartment_url = self.base_url + link.get('href')
                        
                        # Получаем детальную информацию о квартире
                        try:
                            apartment_response = requests.get(
                                apartment_url, 
                                headers={'User-Agent': 'Mozilla/5.0'}
                            )
                            apartment_soup = BeautifulSoup(apartment_response.text, 'html.parser')
                            
                            # Получаем цену
                            price_elem = listing.find('div', class_='a-card__price')
                            price = float(''.join(filter(str.isdigit, price_elem.text.strip()))) if price_elem else 0
                            
                            # Получаем адрес и другие детали
                            address_elem = apartment_soup.find('div', class_='offer__location')
                            if address_elem:
                                address_text = address_elem.text.strip()
                                # Парсим адрес
                                district = None
                                street = None
                                complex_name = None
                                
                                # Ищем район
                                district_elem = apartment_soup.find('div', text=lambda t: t and 'р-н' in t)
                                if district_elem:
                                    district = district_elem.text.strip()
                                
                                # Ищем улицу
                                street_elem = apartment_soup.find('div', text=lambda t: t and 'ул.' in t)
                                if street_elem:
                                    street = street_elem.text.strip()
                                
                                # Ищем ЖК
                                complex_elem = apartment_soup.find('div', text=lambda t: t and 'ЖК' in t)
                                if complex_elem:
                                    complex_name = complex_elem.text.strip()
                            
                            apartments.append({
                                'url': apartment_url,
                                'price': price,
                                'rooms': room,
                                'city': city,
                                'district': district,
                                'street': street,
                                'complex_name': complex_name
                            })
                        except Exception as e:
                            print(f"Error parsing apartment details: {e}")
                            continue
                            
            except Exception as e:
                print(f"Error scraping page: {e}")
                
        return apartments 