#!/usr/bin/env python3
import re
import copy
import datetime
import configmanager
import urllib.parse
import urllib.request
from bs4 import BeautifulSoup



######################## Output Functions ########################

def print_transits(transits):
  """Print transits in a human readable way.

  Args:
      transits (array): Transit dictionaries
  """
  for transit in transits:
    print(transit["object"])
    if "n_samples" in transit:
      print(transit["n_samples"])
    print(transit["mag_depth"])
    print(f"{transit['begin']['time']} @ {transit['begin']['elevation']}°")
    print(f"{transit['center']['time']} @ {transit['center']['elevation']}°")
    print(f"{transit['end']['time']} @ {transit['end']['elevation']}°")
    print()



def print_transits_csv(transits):
  """Print transits in CSV format.

  Args:
      transits (array): Transit dictionaries
  """
  datetime_format = "%Y-%m-%d %H:%M"
  dt = datetime.timedelta(hours=2)
  tz = datetime.timezone(dt)

  header = ["object", "mag_depth", "n_samples", "begin time (cest)", "begin elevation", "center time (cest)", "center elevation", "end time (cest)", "end elevation"]
  print(";".join(header))
  for transit in transits:
    data = [
      transit["object"],
      str(transit["mag_depth"]),
      str(transit["n_samples"]),
      transit["begin"]["time"].astimezone(tz).strftime(datetime_format),
      str(transit["begin"]["elevation"]),
      transit["center"]["time"].astimezone(tz).strftime(datetime_format),
      str(transit["center"]["elevation"]),
      transit["end"]["time"].astimezone(tz).strftime(datetime_format),
      str(transit["end"]["elevation"]),
    ]
    print(";".join(data))



######################## Filter Functions ########################

def filter_time(transit, config):
  """Filter function to remove transits lying outside of the
  configured time window.

  Args:
      transit (dict): A dictionary with information on a transit.
      config (dict): Global configuration

  Returns:
      bool: False if this transit should be discarded, True otherwise.
  """
  min_start_time = datetime.time.fromisoformat(config["min_start_time"])
  max_end_time = datetime.time.fromisoformat(config["max_end_time"])
  start_time = transit["begin"]["time"].timetz()
  end_time = transit["end"]["time"].timetz()
  if start_time >= min_start_time and end_time <= max_end_time:
    return True
  return False



def filter_meridian_flip(transit):
  """Filter function to remove transits that cross the meridian.
  This is because the ATUS telecope needs to flip in this case,
  resulting in an observation gap.

  Args:
      transit (dict): A dictionary with information on a transit.

  Returns:
      bool: False if this transit should be discarded, True otherwise.
  """
  be = transit["begin"]["elevation"]
  ce = transit["center"]["elevation"]
  ee = transit["end"]["elevation"]
  if be < ce and ee < ce:
    return False
  return True



def filter_elevation(transit, config):
  """Filter function to remove transits that are too near to the horizon.

  Args:
      transit (dict): A dictionary with information on a transit.
      config (dict): Global configuration

  Returns:
      bool: False if  this transit should be discarded, True otherwise.
  """
  if transit["begin"]["elevation"] < config["elevation_threshold"]:
    return False
  if transit["end"]["elevation"] < config["elevation_threshold"]:
    return False
  if transit["center"]["elevation"] < config["elevation_threshold"]:
    return False
  return True



######################## Everything else ########################

def get_database_sample_number(config, star_and_planet):
  """Get the number of datasets uploaded to the Exoplanet Tranit
  Database for a specific planet.

  Args:
      config (dict): Global configuration
      star_and_planet (string): Example: "KELT-4A B"

  Returns:
      int: The number of samples.
  """
  star = star_and_planet[:-2]
  planet = star_and_planet[-1]
  get_params = urllib.parse.urlencode({"STARNAME": star, "PLANET": planet})
  url = "{}?{}".format(config["planet_base_url"], get_params)
  req =  urllib.request.Request(url)
  with urllib.request.urlopen(req) as resp:
    charset = resp.info().get_content_charset()
    html = resp.read().decode(charset)
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("form", {"action": "etd.php"}).find("table")
    n_samples = table.findAll("tr")[1].findAll("td")[3].string
    return int(n_samples)



def main():
  config = configmanager.readConfig()

  transits = []
  transit_template = {
    "begin": {},
    "center": {},
    "end": {}
  }

  get_params = urllib.parse.urlencode({
    "init": "2023-06-19",
    "till": "2023-06-23",
    "f": "userdefined"
  })
  url = "{}?{}".format(config["base_url"], get_params)
  req =  urllib.request.Request(url)

  # Telescope coordinates are passed via cookie.
  lon = config["longitude"]
  lat = config["latitude"]
  req.add_header("Cookie", f"cookiedelka={lon}; cookiesirka={lat}")

  with urllib.request.urlopen(req) as resp:
    charset = resp.info().get_content_charset()
    html = resp.read().decode(charset)
    year = datetime.date.today().year
    soup = BeautifulSoup(html, "html.parser")
    # Find table with transits and iterate over rows.
    for tr in soup.find("div", class_="center").find("table").findAll("tr", {"valign": "top"}):
      tds = tr.findAll("td")
      a = tr.find("a")
      if a == None:
        continue

      # Extract transit data into dictionary.
      transit = copy.deepcopy(transit_template)
      transit["object"] = a.string
      transit["mag_depth"] = float(tds[6].get_text())

      # Parse date, time and elevation of transit center.
      center_text = tds[2].get_text()
      # Example pattern: 08.06. 11:0969°,NE
      res = re.search("^([0-9]{2})\.([0-9]{2})\. ([0-9]{1,2}):([0-9]{2})(-?[0-9]{1,2})°", center_text)
      if res:
        g = res.groups()
        day = int(g[0])
        month = int(g[1])
        hour = int(g[2])
        minute = int(g[3])
        elevation = int(g[4])
        transit["center"]["time"] = datetime.datetime(year, month, day, hour, minute, tzinfo=datetime.timezone.utc)
        transit["center"]["elevation"] = elevation
      else:
        print("Could not parse string '{center_text}'")
        return


      # Parse time and elevation of transit beginning and end.
      def extractStartEndTimes(text, dict_key):
        # Example pattern: 10:0310°,NE
        res = re.search("^([0-9]{1,2}):([0-9]{2})(-?[0-9]{1,2})°", text)
        if res:
          g = res.groups()
          hour = int(g[0])
          minute = int(g[1])
          elevation = int(g[2])
          transit[dict_key]["time"] = datetime.datetime(year, month, day, hour, minute, tzinfo=datetime.timezone.utc)
          transit[dict_key]["elevation"] = elevation

      extractStartEndTimes(tds[1].get_text(), "begin")
      extractStartEndTimes(tds[3].get_text(), "end")
      transits.append(transit)

  # Filter out unsuitable transits.
  transits = filter(lambda t: t["mag_depth"] >= config["min_mag_depth"], transits)
  transits = filter(filter_meridian_flip, transits)
  transits = filter(lambda t: filter_time(t, config), transits)
  transits = filter(lambda t: filter_elevation(t, config), transits)

  # Get number of uploaded transit data sets for each object from website.
  transits = list(transits)
  for transit in transits:
    transit["n_samples"] = get_database_sample_number(config, transit["object"])

  # Sort by least observed.
  transits.sort(key=lambda k: k["n_samples"])

  print_transits_csv(transits)




if __name__ == "__main__":
  main()
