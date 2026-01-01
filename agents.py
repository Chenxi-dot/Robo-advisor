from llm_utils import call_llm

class Agent:
    def __init__(self, name, role, description):
        self.name = name
        self.role = role
        self.description = description

    def analyze(self, stock_name, stock_code, data_context):
        raise NotImplementedError("Subclasses must implement analyze method")

class FundamentalAnalyst(Agent):
    def __init__(self):
        super().__init__("Warren", "Fundamental Analyst", "Focuses on financial health, valuation, and long-term growth.")

    def analyze(self, stock_name, stock_code, data_context):
        system_prompt = f"""You are {self.name}, a {self.role}. {self.description}
        Your goal is to analyze the provided financial data for {stock_name} ({stock_code}) and provide a professional investment opinion.
        Focus on:
        1. Valuation (PE, PB, Market Cap)
        2. Financial Performance (Revenue, Profit trends)
        3. Industry Position
        
        Output format: Markdown. Be concise but insightful.
        """
        
        prompt = f"""
        Please analyze {stock_name} ({stock_code}) based on the following data:
        
        Basic Info:
        {data_context.get('basic_info', 'N/A')}
        
        Financial Summary (Recent):
        {data_context.get('financial_summary', 'N/A')}
        
        Industry Comparison:
        {data_context.get('industry_comparison', 'N/A')}
        
        Provide your analysis:
        """
        return call_llm(prompt, system_prompt)

class TechnicalAnalyst(Agent):
    def __init__(self):
        super().__init__("Chartist", "Technical Analyst", "Focuses on price action, trends, volume, and technical indicators.")

    def analyze(self, stock_name, stock_code, data_context):
        system_prompt = f"""You are {self.name}, a {self.role}. {self.description}
        Your goal is to analyze the technical patterns for {stock_name} ({stock_code}).
        Focus on:
        1. Trend Analysis (Moving Averages)
        2. Volume Analysis
        3. Support and Resistance levels (estimated)
        4. Recent price action
        
        Output format: Markdown. Use bullet points.
        """
        
        prompt = f"""
        Please analyze {stock_name} ({stock_code}) based on the following market data:
        
        Recent Price Action (Last 5 days):
        {data_context.get('price_action', 'N/A')}
        
        Moving Averages:
        {data_context.get('moving_averages', 'N/A')}
        
        Volume Info:
        {data_context.get('volume_info', 'N/A')}
        
        Provide your technical outlook:
        """
        return call_llm(prompt, system_prompt)

class NewsAnalyst(Agent):
    def __init__(self):
        super().__init__("Scoop", "News & Sentiment Analyst", "Focuses on market sentiment, news, and public opinion.")

    def analyze(self, stock_name, stock_code, data_context):
        system_prompt = f"""You are {self.name}, a {self.role}. {self.description}
        Your goal is to gauge the sentiment for {stock_name} ({stock_code}).
        Focus on:
        1. Recent News Headlines
        2. Company Announcements
        3. Retail Investor Sentiment (Guba comments)
        
        Output format: Markdown. Highlight key events.
        """
        
        prompt = f"""
        Please analyze the sentiment for {stock_name} ({stock_code}) based on:
        
        Recent Notices/Announcements:
        {data_context.get('notices', 'N/A')}
        
        Recent News/Comments:
        {data_context.get('comments', 'N/A')}
        
        Provide your sentiment analysis:
        """
        return call_llm(prompt, system_prompt)

class RiskManager(Agent):
    def __init__(self):
        super().__init__("Prudence", "Risk Manager", "Focuses on identifying potential risks and downsides.")

    def analyze(self, stock_name, stock_code, data_context):
        system_prompt = f"""You are {self.name}, a {self.role}. {self.description}
        Your job is to be the devil's advocate and point out risks for {stock_name} ({stock_code}).
        Focus on:
        1. Volatility risks
        2. Financial red flags (if any)
        3. Market/Industry risks
        
        Output format: Markdown. Be direct and cautionary.
        """
        
        prompt = f"""
        Identify risks for {stock_name} ({stock_code}) based on:
        
        Financial Data:
        {data_context.get('financial_summary', 'N/A')}
        
        Market Data:
        {data_context.get('price_action', 'N/A')}
        
        News/Notices:
        {data_context.get('notices', 'N/A')}
        
        Provide your risk assessment:
        """
        return call_llm(prompt, system_prompt)
