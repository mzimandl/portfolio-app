import { Table, TableBody, TableHead, TableContainer, TableRow, TableCell, Box, Typography, Card, CardHeader, CardContent, Grid2 as Grid, FormGroup, Switch, FormControlLabel } from '@mui/material';
import { AbstractSection, SectionProps } from '../common';


interface OverviewDataRow {
    ticker: string;
    type: string;
    currency: string;
    last_price: number;
    average_price: number;
    investment: number;
    volume: number;
    value: number;
    fees: number;
    value_profit: number;
    fx_profit: number;
    withdraw: number;
    total_profit: number;
    rewards: number;
    dividends: number;
    dividend_currency: string;
}

interface DividendsDataRow {
    ticker: string;
    currency: string;
    dividends: number;
}

type OverviewResponse = Array<OverviewDataRow>;
type DividendsResponse = {[ticker:string]:DividendsDataRow};

interface OverviewState {
    types: Array<string>;
    groupByType: boolean;
    // aggregates
    investment: number;
    fees: number;
    value: number;
    profit: number;
    savingsDeposit: number;
    savingsValue: number;
    // overview lines
    overview: Array<OverviewDataRow>;
    dividends: DividendsResponse;
    
}

interface OverviewProps {}

export class Overview extends AbstractSection<OverviewProps, OverviewState> {

    sectionName = () => 'Overview';

    constructor(props: OverviewProps & SectionProps) {
        super(props);
        this.state = {
            investment: 0,
            fees: 0,
            value: 0,
            profit: 0,
            savingsDeposit: 0,
            savingsValue: 0,
            overview: [],
            dividends: {},
            types: [],
            groupByType: false,
        };
    }

    componentDidMount() {
        super.componentDidMount();
        this.props.displayProgressBar(true)
        this.loadOverview().then(() =>
            this.loadDividends().then(() =>
                this.props.displayProgressBar(false)
            )
        );
    }

    loadOverview() {
        return fetch('/overview/get')
            .then<OverviewResponse>(res => res.json())
            .then(overview => {
                const types: Array<string> = [];
                overview.forEach(v => {
                    if (!types.includes(v.type)) types.push(v.type);
                });
                types.sort();
                this.setState({
                    overview,
                    types,
                    investment: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev : prev + cur.investment, 0),
                    fees: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev : prev + cur.fees, 0),
                    value: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev : prev + cur.value, 0),
                    profit: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev : prev + cur.total_profit, 0),
                    savingsDeposit: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev + cur.investment : prev, 0),
                    savingsValue: overview.reduce((prev, cur, i) => cur.type === 'savings' ? prev + cur.value : prev, 0),
                });
            });
    }

    loadDividends() {
        return fetch('/dividends/calc')
            .then<DividendsResponse>(res => res.json())
            .then(dividends => {
                this.setState({dividends});
            });
    }

    render() {
        return (
            <Box>
                <Grid container spacing={2}>
                    <Grid size={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Investment'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.investment)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid size={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Fees'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.fees)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid size={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Value'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.value)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid size={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Profit'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.profit)} ({this.formatPercents(this.state.profit/this.state.investment)})
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid size={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Savings Deposit'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.savingsDeposit)}
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                    <Grid size={2}>
                        <Card elevation={3}>
                            <CardHeader title={'Savings Value'} />
                            <CardContent>
                                <Typography sx={{ mb: 1.5 }} color="text.secondary">
                                    {this.formatCurrency(this.state.savingsValue)} ({this.formatPercents((this.state.savingsValue-this.state.savingsDeposit)/this.state.savingsValue)})
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                </Grid>

                <FormGroup>
                    <FormControlLabel control={<Switch checked={this.state.groupByType} onChange={(e, value) => this.setState({groupByType: value})}/>} label="Group by type" />
                </FormGroup>

                {this.state.groupByType ?
                    this.state.types.map(type =>
                        <Card elevation={3} sx={{marginBottom: '1em'}}>
                            <CardHeader title={type} />
                            <Box>
                                <TableContainer>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>Ticker</TableCell>
                                                <TableCell align='right'>Price</TableCell>
                                                <TableCell align='right'>Volume</TableCell>
                                                <TableCell align='right'>Investment</TableCell>
                                                <TableCell align='right'>Return</TableCell>
                                                <TableCell align='right'>Value</TableCell>
                                                <TableCell colSpan={3} align='center'>Profit</TableCell>
                                                <TableCell align='center'>Dividends</TableCell>
                                                <TableCell align='right'>Fees</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {this.state.overview.filter(item => item.type === type).map((item, i) =>
                                                <TableRow key={i} sx={{backgroundColor: item.total_profit < 0 ? 'rgba(255,0,0,0.25)' : 'rgba(0,255,0,0.25)'}}>
                                                    <TableCell>{item.ticker}</TableCell>
                                                    <TableCell align='right' style={{fontSize: "0.6em"}}>
                                                        {item.last_price ? "last:" : null} {this.formatCurrency(item.last_price, {currency: item.currency})}
                                                        <br/>
                                                        {item.average_price ? "avg:" : null} {this.formatCurrency(item.average_price, {currency: item.currency})}
                                                    </TableCell>
                                                    <TableCell align='right'>{item.volume ? item.volume : null}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.investment)}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.withdraw)}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.value)}</TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.total_profit, {signed: true})}</TableCell>
                                                    <TableCell align='left' style={{fontSize: "0.6em"}}>
                                                        {item.value_profit ? "value" : null} {this.formatCurrency(item.value_profit, {signed: true})}
                                                        <br/>
                                                        {item.fx_profit ? "fx" : null} {this.formatCurrency(item.fx_profit, {signed: true})}
                                                        <br/>
                                                        {item.rewards ? "rewards" : null} {this.formatCurrency(item.rewards, {signed: true})}
                                                    </TableCell>
                                                    <TableCell align='center'>{this.formatPercents(item.total_profit/item.investment)}</TableCell>
                                                    <TableCell align='right'>
                                                        {item.dividends ? "payed:" : null} {item.dividends ? this.formatCurrency(item.dividends, {currency: item.dividend_currency}) : null}
                                                        <br/>
                                                        {this.state.dividends[item.ticker] ? "calc:" : null} {this.state.dividends[item.ticker] ? this.formatCurrency(this.state.dividends[item.ticker].dividends, {currency: this.state.dividends[item.ticker].currency}) : null}
                                                    </TableCell>
                                                    <TableCell align='right'>{this.formatCurrency(item.fees)}</TableCell>
                                                </TableRow>
                                            )}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Box>
                        </Card>
                    ) :
                    <Card elevation={3}>
                        <Box>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>Ticker</TableCell>
                                            <TableCell align='right'>Price</TableCell>
                                            <TableCell align='right'>Volume</TableCell>
                                            <TableCell align='right'>Investment</TableCell>
                                            <TableCell align='right'>Return</TableCell>
                                            <TableCell align='right'>Value</TableCell>
                                            <TableCell colSpan={3} align='center'>Profit</TableCell>
                                            <TableCell align='center'>Dividends</TableCell>
                                            <TableCell align='right'>Fees</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {this.state.overview.map((item, i) =>
                                            <TableRow key={i} sx={{backgroundColor: item.total_profit < 0 ? 'rgba(255,0,0,0.25)' : 'rgba(0,255,0,0.25)'}}>
                                                <TableCell>{item.ticker}</TableCell>
                                                <TableCell align='right' style={{fontSize: "0.6em"}}>
                                                    {item.last_price ? "last:" : null} {this.formatCurrency(item.last_price, {currency: item.currency})}
                                                    <br/>
                                                    {item.average_price ? "avg:" : null} {this.formatCurrency(item.average_price, {currency: item.currency})}
                                                </TableCell>
                                                <TableCell align='right'>{item.volume ? item.volume : null}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.investment)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.withdraw)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.value)}</TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.total_profit, {signed: true})}</TableCell>
                                                <TableCell align='left' style={{fontSize: "0.6em"}}>
                                                    {item.value_profit ? "value" : null} {this.formatCurrency(item.value_profit, {signed: true})}
                                                    <br/>
                                                    {item.fx_profit ? "fx" : null} {this.formatCurrency(item.fx_profit, {signed: true})}
                                                    <br/>
                                                    {item.rewards ? "rewards" : null} {this.formatCurrency(item.rewards, {signed: true})}
                                                </TableCell>
                                                <TableCell align='center'>{this.formatPercents(item.total_profit/item.investment)}</TableCell>
                                                <TableCell align='right'>
                                                    {item.dividends ? "payed:" : null} {item.dividends ? this.formatCurrency(item.dividends, {currency: item.dividend_currency}) : null}
                                                    <br/>
                                                    {this.state.dividends[item.ticker] ? "calc:" : null} {this.state.dividends[item.ticker] ? this.formatCurrency(this.state.dividends[item.ticker].dividends, {currency: this.state.dividends[item.ticker].currency}) : null}
                                                </TableCell>
                                                <TableCell align='right'>{this.formatCurrency(item.fees)}</TableCell>
                                            </TableRow>
                                        )}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </Box>
                    </Card>
                }
            </Box>
        )
    }
}